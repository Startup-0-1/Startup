from datetime import datetime, date, time, timedelta
from functools import wraps

import stripe

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    login as auth_login,
    logout as auth_logout,
)
from django.contrib.auth.decorators import login_required
from django.http import (
    HttpResponseBadRequest,
    HttpResponseNotAllowed,
    HttpResponseForbidden,
)
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import update_session_auth_hash
from django.db import IntegrityError

from .models import User, Payment, Appointment, DoctorAvailability, Document, Prescription
from .serializers import (
    UserSerializer,
    PatientSignupSerializer,
    DoctorSignupSerializer,
    LoginSerializer,
)

# ===========================
# STRIPE CONFIG
# ===========================

stripe.api_key = settings.STRIPE_SECRET_KEY

# ===========================
# ROLE-BASED ACCESS DECORATORS
# ===========================


def role_required(required_role):
    """
    Require a given role (patient/doctor/admin).
    Admins always bypass and are allowed.
    """

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            if request.user.role == "admin" or request.user.role == required_role:
                return view_func(request, *args, **kwargs)
            return HttpResponseForbidden("You do not have permission to access this resource.")

        return _wrapped_view

    return decorator


# ===========================
# LOGOUT VIEW
# ===========================


@login_required
def logout_view(request):
    auth_logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("welcome")


# ===========================
# INPUT NORMALIZATION HELPERS
# ===========================


def normalize_dob_input(raw: str | None) -> str | None:
    """
    Accepts things like:
      - '06/27/1992'
      - '06-27-1992'
      - '06271992'
    and normalizes to 'YYYY-MM-DD' for the serializer/DB.
    """
    if not raw:
        return raw
    raw = raw.strip()
    digits = "".join(ch for ch in raw if ch.isdigit())

    # If user types 06271992 → interpret as MMDDYYYY
    if len(digits) == 8:
        mm = digits[0:2]
        dd = digits[2:4]
        yyyy = digits[4:8]
        try:
            dt = datetime.strptime(f"{mm}/{dd}/{yyyy}", "%m/%d/%Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return raw  # let serializer complain

    # Try a couple of common formats
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return raw  # if totally invalid, serializer will handle error


# ===========================
# DOCTOR AVAILABILITY / SLOTS
# ===========================

SLOT_MINUTES = 30
SLOT_DELTA = timedelta(minutes=SLOT_MINUTES)


def get_available_slots_for_doctor(doctor: User, target_date: date):
    """
    Returns a list of (start_dt, end_dt) datetimes for 30-minute slots
    for a doctor on a given date, based on DoctorAvailability windows,
    excluding already-booked (non-cancelled) Appointment.scheduled_for slots,
    and never exposing slots that are in the past.
    """
    windows = DoctorAvailability.objects.filter(
        doctor=doctor,
        date=target_date,
    ).order_by("start_time")

    if not windows.exists():
        return []

    tz = timezone.get_current_timezone()

    # aware begin/end of day
    start_of_day = timezone.make_aware(
        datetime.combine(target_date, time(0, 0)),
        tz,
    )
    end_of_day = timezone.make_aware(
        datetime.combine(target_date, time(23, 59, 59)),
        tz,
    )

    # booked = any status EXCEPT 'cancelled'
    booked = set(
        Appointment.objects.filter(
            doctor=doctor,
            scheduled_for__gte=start_of_day,
            scheduled_for__lte=end_of_day,
        )
        .exclude(status="cancelled")
        .values_list("scheduled_for", flat=True)
    )

    now = timezone.now()

    slots = []
    for w in windows:
        current_start = timezone.make_aware(
            datetime.combine(target_date, w.start_time),
            tz,
        )
        window_end = timezone.make_aware(
            datetime.combine(target_date, w.end_time),
            tz,
        )

        while current_start + SLOT_DELTA <= window_end:
            current_end = current_start + SLOT_DELTA

            # only show future, non-booked slots
            if current_start > now and current_start not in booked:
                slots.append((current_start, current_end))

            current_start = current_end

    return slots


# ===========================
# GROUPING HELPERS
# ===========================


def group_appointments_for_patient(qs):
    """
    Group a patient's appointments into contiguous 30-min blocks
    per doctor/date/reason/status/payment.
    """
    qs = qs.order_by("doctor__id", "scheduled_for")
    blocks = []
    current = None

    for appt in qs:
        day = appt.scheduled_for.date()
        if current is None:
            current = {
                "doctor": appt.doctor,
                "patient": appt.patient,
                "date": day,
                "start": appt.scheduled_for,
                "end": appt.scheduled_for + SLOT_DELTA,
                "status": appt.status,
                "reason": appt.reason,
                "payment": appt.payment,
                "slot_ids": [str(appt.id)],
                "slots": [appt],
            }
            continue

        last_slot_start = current["slots"][-1].scheduled_for

        same_doctor = appt.doctor_id == current["doctor"].id
        same_patient = appt.patient_id == current["patient"].id
        same_date = day == current["date"]
        same_status = appt.status == current["status"]
        same_reason = appt.reason == current["reason"]
        same_payment = appt.payment_id == (current["payment"].id if current["payment"] else None)
        contiguous = appt.scheduled_for == last_slot_start + SLOT_DELTA

        if (
            same_doctor
            and same_patient
            and same_date
            and same_status
            and same_reason
            and same_payment
            and contiguous
        ):
            current["slots"].append(appt)
            current["slot_ids"].append(str(appt.id))
            current["end"] = appt.scheduled_for + SLOT_DELTA
        else:
            blocks.append(current)
            current = {
                "doctor": appt.doctor,
                "patient": appt.patient,
                "date": day,
                "start": appt.scheduled_for,
                "end": appt.scheduled_for + SLOT_DELTA,
                "status": appt.status,
                "reason": appt.reason,
                "payment": appt.payment,
                "slot_ids": [str(appt.id)],
                "slots": [appt],
            }

    if current is not None:
        blocks.append(current)

    return blocks


def group_appointments_for_doctor(qs):
    """
    Group a doctor's appointments into contiguous 30-min blocks
    per patient/date/reason/status/payment.
    """
    qs = qs.order_by("patient__id", "scheduled_for")
    blocks = []
    current = None

    for appt in qs:
        day = appt.scheduled_for.date()
        if current is None:
            current = {
                "doctor": appt.doctor,
                "patient": appt.patient,
                "date": day,
                "start": appt.scheduled_for,
                "end": appt.scheduled_for + SLOT_DELTA,
                "status": appt.status,
                "reason": appt.reason,
                "payment": appt.payment,
                "slot_ids": [str(appt.id)],
                "slots": [appt],
            }
            continue

        last_slot_start = current["slots"][-1].scheduled_for

        same_doctor = appt.doctor_id == current["doctor"].id
        same_patient = appt.patient_id == current["patient"].id
        same_date = day == current["date"]
        same_status = appt.status == current["status"]
        same_reason = appt.reason == current["reason"]
        same_payment = appt.payment_id == (current["payment"].id if current["payment"] else None)
        contiguous = appt.scheduled_for == last_slot_start + SLOT_DELTA

        if (
            same_doctor
            and same_patient
            and same_date
            and same_status
            and same_reason
            and same_payment
            and contiguous
        ):
            current["slots"].append(appt)
            current["slot_ids"].append(str(appt.id))
            current["end"] = appt.scheduled_for + SLOT_DELTA
        else:
            blocks.append(current)
            current = {
                "doctor": appt.doctor,
                "patient": appt.patient,
                "date": day,
                "start": appt.scheduled_for,
                "end": appt.scheduled_for + SLOT_DELTA,
                "status": appt.status,
                "reason": appt.reason,
                "payment": appt.payment,
                "slot_ids": [str(appt.id)],
                "slots": [appt],
            }

    if current is not None:
        blocks.append(current)

    return blocks


# ===========================
# HTML VIEWS (welcome / auth)
# ===========================


def welcome_page(request):
    """
    Landing / dashboard page.
    """
    return render(request, "core/welcome.html")


def login_page(request):
    """
    HTML login page.
    """
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, username=email, password=password)
        if user is not None:
            auth_login(request, user)
            messages.success(request, f"Logged in as {user.email} ({user.role})")
            return redirect("welcome")
        else:
            messages.error(request, "Invalid email or password.")

    return render(request, "core/login.html")

from django.utils import timezone  # make sure this is imported at the top

# ===========================
# TIMEZONE SETTINGS VIEW
# ===========================

@login_required
def timezone_settings_view(request):
    return redirect("settings-view")

# ===========================
# SIGNUP VIEWS
# ===========================
def patient_signup_page(request):
    """
    HTML signup page for patients.
    """
    if request.method == "POST":
        dob_raw = request.POST.get("date_of_birth")
        dob_normalized = normalize_dob_input(dob_raw)

        data = {
            "email": request.POST.get("email"),
            "password": request.POST.get("password"),
            "password_confirm": request.POST.get("password_confirm"),
            "full_name": request.POST.get("full_name"),
            "date_of_birth": dob_normalized,
            "gender": request.POST.get("gender"),
            "contact_number": request.POST.get("contact_number"),
            "address": request.POST.get("address"),
            "emergency_contact": request.POST.get("emergency_contact"),
            "insurance_provider": request.POST.get("insurance_provider"),
            "insurance_policy_number": request.POST.get("insurance_policy_number"),
        }
        serializer = PatientSignupSerializer(data=data)
        if serializer.is_valid():
            user = serializer.save()
            auth_login(request, user)
            messages.success(request, "Patient account created and logged in.")
            return redirect("welcome")
        else:
            for field, errs in serializer.errors.items():
                for err in errs:
                    messages.error(request, f"{field}: {err}")

    return render(request, "core/signup_patient.html")


def doctor_signup_page(request):
    """
    HTML signup page for doctors.
    """
    if request.method == "POST":
        data = {
            "email": request.POST.get("email"),
            "password": request.POST.get("password"),
            "password_confirm": request.POST.get("password_confirm"),
            "full_name": request.POST.get("full_name"),
            "specialization": request.POST.get("specialization"),
            "license_number": request.POST.get("license_number"),
            "years_of_experience": request.POST.get("years_of_experience"),
            "contact_number": request.POST.get("contact_number"),
            "clinic_name": request.POST.get("clinic_name"),
            "clinic_address": request.POST.get("clinic_address"),
            "bio": request.POST.get("bio"),
        }
        serializer = DoctorSignupSerializer(data=data)
        if serializer.is_valid():
            user = serializer.save()
            auth_login(request, user)
            messages.success(request, "Doctor account created and logged in.")
            return redirect("welcome")
        else:
            for field, errs in serializer.errors.items():
                for err in errs:
                    messages.error(request, f"{field}: {err}")

    return render(request, "core/signup_doctor.html")


# ===========================
# PATIENT APPOINTMENT VIEWS
# ===========================


@role_required("patient")
def patient_appointment_list(request):
    """
    Show grouped appointments for the logged-in patient.
    Each block = one row (start–end).
    """
    qs = Appointment.objects.filter(patient=request.user).order_by("scheduled_for")
    blocks = group_appointments_for_patient(qs)
    return render(
        request,
        "core/appointments_patient_list.html",
        {"appointment_blocks": blocks},
    )


@role_required("patient")
def patient_appointment_create(request):
    """
    Two-step flow:
    - Step 1 (GET): choose doctor + date → see available slots
    - Step 2 (POST): choose one or more 30-minute slots → create one Appointment per slot
    """
    doctors = User.objects.filter(role="doctor", is_active=True).order_by("email")

    doctor_id_get = request.GET.get("doctor_id")
    date_str_get = request.GET.get("date")

    selected_doctor = None
    selected_date = None
    available_slots = []

    if doctor_id_get and date_str_get:
        try:
            selected_doctor = User.objects.get(id=doctor_id_get, role="doctor")
        except User.DoesNotExist:
            selected_doctor = None
            messages.error(request, "Selected doctor not found.")
        else:
            try:
                selected_date = datetime.strptime(date_str_get, "%Y-%m-%d").date()
            except ValueError:
                selected_date = None
                messages.error(request, "Invalid date.")
            else:
                available_slots = get_available_slots_for_doctor(selected_doctor, selected_date)

    if request.method == "POST":
        doctor_id_post = request.POST.get("doctor_id")
        date_str_post = request.POST.get("date")
        slot_start_strs = request.POST.getlist("slot_start")
        reason = request.POST.get("reason")

        if not doctor_id_post or not date_str_post:
            messages.error(request, "Please select a doctor and date.")
            return redirect("patient-appointment-create")

        if not slot_start_strs:
            messages.error(request, "Please select at least one time slot.")
            return redirect(
                f"{reverse('patient-appointment-create')}?doctor_id={doctor_id_post}&date={date_str_post}"
            )

        try:
            doctor = User.objects.get(id=doctor_id_post, role="doctor")
        except User.DoesNotExist:
            messages.error(request, "Selected doctor not found.")
            return redirect("patient-appointment-create")

        try:
            selected_date = datetime.strptime(date_str_post, "%Y-%m-%d").date()
        except ValueError:
            messages.error(request, "Invalid date.")
            return redirect("patient-appointment-create")

        created_count = 0
        tz = timezone.get_current_timezone()

        for slot_start_str in slot_start_strs:
            try:
                naive_slot_start = datetime.strptime(slot_start_str, "%Y-%m-%dT%H:%M")
            except ValueError:
                continue

            slot_start = timezone.make_aware(naive_slot_start, tz)

            if Appointment.objects.filter(doctor=doctor, scheduled_for=slot_start).exclude(
                status="cancelled"
            ).exists():
                continue

            Appointment.objects.create(
                patient=request.user,
                doctor=doctor,
                scheduled_for=slot_start,
                reason=reason,
                status="requested",
            )
            created_count += 1

        if created_count == 0:
            messages.error(
                request,
                "None of the selected time slots were available. Please choose different slots.",
            )
            return redirect(
                f"{reverse('patient-appointment-create')}?doctor_id={doctor.id}&date={date_str_post}"
            )

        messages.success(
            request,
            f"Appointment requested for {created_count} time slot(s).",
        )
        return redirect("patient-appointments")

    context = {
        "doctors": doctors,
        "selected_doctor": selected_doctor,
        "selected_date": selected_date,
        "available_slots": available_slots,
    }
    return render(request, "core/appointments_patient_create.html", context)


# ===========================
# DOCTOR APPOINTMENT VIEWS
# ===========================


@role_required("doctor")
def doctor_appointment_list(request):
    """
    Show grouped appointments assigned to the logged-in doctor.
    """
    qs = Appointment.objects.filter(doctor=request.user).order_by("scheduled_for")
    blocks = group_appointments_for_doctor(qs)

    # build 30-min ranges for checkbox UI
    for block in blocks:
        slot_ranges = []
        for appt in block["slots"]:
            slot_ranges.append(
                {
                    "id": appt.id,
                    "start": appt.scheduled_for,
                    "end": appt.scheduled_for + SLOT_DELTA,
                }
            )
        block["slot_ranges"] = slot_ranges

    return render(
        request,
        "core/appointments_doctor_list.html",
        {"appointment_blocks": blocks},
    )


@role_required("doctor")
def doctor_update_appointments(request):
    """
    Handle doctor actions:
    - mode = 'set_status': change status for all slot_ids
    - mode = 'cancel_slots': cancel selected slot_ids
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    mode = request.POST.get("mode")
    slot_ids = request.POST.getlist("slot_ids")

    if not slot_ids:
        messages.error(request, "No slots selected.")
        return redirect("doctor-appointments")

    appointments = list(
        Appointment.objects.filter(id__in=slot_ids, doctor=request.user).order_by("scheduled_for")
    )
    if not appointments:
        messages.error(request, "No matching appointments found.")
        return redirect("doctor-appointments")

    if mode == "set_status":
        new_status = request.POST.get("new_status")
        if new_status not in ["requested", "approved", "rejected", "completed", "cancelled"]:
            messages.error(request, "Invalid status.")
            return redirect("doctor-appointments")

        for appt in appointments:
            appt.status = new_status
            appt.save()

        messages.success(request, f"Status updated to '{new_status}' for selected appointment block.")
        return redirect("doctor-appointments")

    elif mode == "cancel_slots":
        cancelled_count = 0
        for appt in appointments:
            if appt.status != "cancelled":
                appt.status = "cancelled"
                appt.save()
                cancelled_count += 1

        if cancelled_count == 0:
            messages.info(request, "No slots were cancelled (maybe already cancelled).")
        else:
            messages.success(request, f"Cancelled {cancelled_count} slot(s).")

        return redirect("doctor-appointments")

    else:
        messages.error(request, "Unknown action.")
        return redirect("doctor-appointments")


# ===========================
# PAYMENT VIEWS
# ===========================


@login_required
def payment_page(request):
    amount_cents = 5000
    currency = "usd"

    context = {
        "amount_dollars": amount_cents / 100,
        "currency": currency.upper(),
    }
    return render(request, "core/payment.html", context)


@login_required
def create_checkout_session(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    amount_cents = 5000
    currency = "usd"

    payment = Payment.objects.create(
        user=request.user,
        amount_cents=amount_cents,
        currency=currency,
        status="pending",
        description="Consultation fee",
    )

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": currency,
                        "product_data": {"name": "Consultation fee"},
                        "unit_amount": amount_cents,
                    },
                    "quantity": 1,
                }
            ],
            customer_email=request.user.email,
            success_url=request.build_absolute_uri(
                reverse("payment-success")
            ) + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=request.build_absolute_uri(reverse("payment-cancel")),
        )
    except Exception as e:
        payment.status = "failed"
        payment.save()
        return HttpResponseBadRequest(f"Stripe error: {e}")

    payment.stripe_session_id = session.id
    payment.save()

    return redirect(session.url)


@login_required
def payment_success(request):
    session_id = request.GET.get("session_id")
    if not session_id:
        return HttpResponseBadRequest("Missing session_id")

    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception:
        return HttpResponseBadRequest("Invalid session")

    try:
        payment = Payment.objects.get(stripe_session_id=session.id, user=request.user)
    except Payment.DoesNotExist:
        return HttpResponseBadRequest("Payment not found")

    if session.payment_status == "paid":
        payment.status = "paid"
        payment.save()

    amount_dollars = payment.amount_cents / 100

    return render(
        request,
        "core/payment_success.html",
        {
            "payment": payment,
            "amount_dollars": amount_dollars,
        },
    )


@login_required
def payment_cancel(request):
    return render(request, "core/payment_cancel.html")


# ===========================
# API VIEWS
# ===========================


class PatientSignupView(generics.CreateAPIView):
    serializer_class = PatientSignupSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        auth_login(request, user)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class DoctorSignupView(generics.CreateAPIView):
    serializer_class = DoctorSignupSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        auth_login(request, user)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        auth_login(request, user)
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

# ===========================
# Profile Views
# ===========================
@login_required
def profile_view(request):
    """
    User profile:
    - View core info
    - Update email + profile details
    - Change password
    - Upload profile image (jpg/png)
    """
    user = request.user
    patient_profile = getattr(user, "patient_profile", None)
    doctor_profile = getattr(user, "doctor_profile", None)

    if request.method == "POST":
        action = request.POST.get("action")

        # --- Update basic info / email ---
        if action == "update_profile":
            new_email = request.POST.get("email", "").strip()
            if new_email and new_email != user.email:
                # ensure unique email
                if User.objects.filter(email=new_email).exclude(id=user.id).exists():
                    messages.error(request, "That email address is already in use.")
                else:
                    user.email = new_email
                    user.save()
                    messages.success(request, "Email updated.")

            # PATIENT FIELDS
            if patient_profile:
                patient_profile.full_name = request.POST.get(
                    "full_name", patient_profile.full_name
                )
                patient_profile.date_of_birth = request.POST.get(
                    "date_of_birth", patient_profile.date_of_birth
                )
                patient_profile.gender = request.POST.get(
                    "gender", patient_profile.gender
                )
                patient_profile.contact_number = request.POST.get(
                    "contact_number", patient_profile.contact_number
                )
                patient_profile.address = request.POST.get(
                    "address", patient_profile.address
                )
                patient_profile.emergency_contact = request.POST.get(
                    "emergency_contact", patient_profile.emergency_contact
                )
                patient_profile.insurance_provider = request.POST.get(
                    "insurance_provider", patient_profile.insurance_provider
                )
                patient_profile.insurance_policy_number = request.POST.get(
                    "insurance_policy_number",
                    patient_profile.insurance_policy_number,
                )
                patient_profile.save()

            # DOCTOR FIELDS
            if doctor_profile:
                doctor_profile.full_name = request.POST.get(
                    "full_name", doctor_profile.full_name
                )
                doctor_profile.specialization = request.POST.get(
                    "specialization", doctor_profile.specialization
                )
                doctor_profile.contact_number = request.POST.get(
                    "contact_number", doctor_profile.contact_number
                )
                doctor_profile.clinic_name = request.POST.get(
                    "clinic_name", doctor_profile.clinic_name
                )
                doctor_profile.clinic_address = request.POST.get(
                    "clinic_address", doctor_profile.clinic_address
                )
                doctor_profile.save()

            messages.success(request, "Profile details updated.")

        # --- Change password ---
        elif action == "change_password":
            current_password = request.POST.get("current_password")
            new_password1 = request.POST.get("new_password1")
            new_password2 = request.POST.get("new_password2")

            if not user.check_password(current_password):
                messages.error(request, "Current password is incorrect.")
            elif not new_password1 or new_password1 != new_password2:
                messages.error(request, "New passwords do not match.")
            else:
                user.set_password(new_password1)
                user.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Password changed successfully.")

        # --- Upload profile image ---
        elif action == "upload_image":
            img = request.FILES.get("profile_image")
            if not img:
                messages.error(request, "Please choose an image to upload.")
            else:
                user.profile_image = img
                user.save()
                messages.success(request, "Profile image updated.")

        return redirect("profile")

    context = {
        "user_obj": user,
        "patient_profile": patient_profile,
        "doctor_profile": doctor_profile,
    }
    return render(request, "core/profile.html", context)


# ===========================
# DOCUMENT VIEWS
# ===========================
@login_required
def documents_view(request):
    """
    Simple document portal for now:
    - Shows documents where owner_user = current user
    - Allows upload
    Later you can refine privileges per role.
    """
    if request.method == "POST":
        uploaded_file = request.FILES.get("file")
        doc_type = request.POST.get("document_type", "other")
        file_name = request.POST.get("file_name") or (uploaded_file.name if uploaded_file else None)

        if not uploaded_file:
            messages.error(request, "Please choose a file to upload.")
        else:
            Document.objects.create(
                owner_user=request.user,
                uploaded_by_user=request.user,
                uploader_role=request.user.role,
                file_name=file_name,
                file=uploaded_file,
                document_type=doc_type,
            )
            messages.success(request, "Document uploaded.")

        return redirect("documents")

    docs = Document.objects.filter(owner_user=request.user).order_by("-created_at")
    return render(request, "core/documents.html", {"documents": docs})

# ===========================
# PRESCRIPTION VIEWS
# ===========================
@login_required
def prescriptions_view(request):
    """
    Show prescriptions relevant to the user:
    - patient: prescriptions where patient = user
    - doctor: prescriptions where doctor = user
    - admin: all (for now)
    """
    user = request.user
    if user.role == "patient":
        prescriptions = Prescription.objects.filter(patient=user).order_by("-created_at")
    elif user.role == "doctor":
        prescriptions = Prescription.objects.filter(doctor=user).order_by("-created_at")
    else:  # admin
        prescriptions = Prescription.objects.all().order_by("-created_at")

    return render(request, "core/prescriptions.html", {"prescriptions": prescriptions})
# ===========================
# Settings View
# ===========================
@login_required
def settings_view(request):
    """
    Settings:
    - Theme (light/dark)
    - Location tracking toggle
    - Time zone selection (moved here from standalone page)
    """
    user = request.user

    if request.method == "POST":
        theme = request.POST.get("theme")
        loc_tracking = request.POST.get("location_tracking") == "on"
        tz_name = request.POST.get("timezone")

        if theme in ("light", "dark"):
            user.theme_preference = theme
        user.location_tracking_enabled = loc_tracking

        if tz_name:
            try:
                timezone.activate(tz_name)
                request.session["django_timezone"] = tz_name
            except Exception:
                messages.error(request, "Invalid time zone selected.")

        user.save()
        messages.success(request, "Settings updated.")
        return redirect("settings-view")

    current_tz = timezone.get_current_timezone_name()
    context = {
        "current_tz": current_tz,
        "current_theme": user.theme_preference,
        "location_tracking_enabled": user.location_tracking_enabled,
    }
    return render(request, "core/settings.html", context)

# ===========================
# Doctor Timetable/Availability Views
# ===========================
@role_required("doctor")
def doctor_schedule_view(request):
    """
    Doctor's schedule management:
    - For each day, doctor sets open/close time.
    - Creates/updates DoctorAvailability windows.
    - Patients see 30-min slots generated from these windows.
    - Doctor can delete individual future, unbooked 30-min slots.
    """
    doctor = request.user

    # Date selected for viewing slots
    date_param = request.GET.get("date") or request.POST.get("selected_date")
    selected_date = None
    if date_param:
        try:
            selected_date = datetime.strptime(date_param, "%Y-%m-%d").date()
        except ValueError:
            selected_date = None

    if request.method == "POST":
        action = request.POST.get("action", "save_window")

        # --- DELETE A SINGLE 30-MIN SLOT ---
        if action == "delete_slot":
            slot_start_str = request.POST.get("slot_start")
            if not slot_start_str:
                messages.error(request, "Missing slot to delete.")
                return redirect(request.path + (f"?date={date_param}" if date_param else ""))

            try:
                # format: 2025-12-04T14:30
                naive_slot_start = datetime.strptime(slot_start_str, "%Y-%m-%dT%H:%M")
            except ValueError:
                messages.error(request, "Invalid slot timestamp.")
                return redirect(request.path + (f"?date={date_param}" if date_param else ""))

            tz = timezone.get_current_timezone()
            slot_start = timezone.make_aware(naive_slot_start, tz)
            slot_end = slot_start + SLOT_DELTA

            # 1) Can't delete past slots
            if slot_start <= timezone.now():
                messages.error(request, "Cannot delete a past slot.")
                return redirect(request.path + f"?date={slot_start.date().isoformat()}")

            # 2) Can't delete booked slots
            if Appointment.objects.filter(
                doctor=doctor,
                scheduled_for=slot_start,
            ).exclude(status="cancelled").exists():
                messages.error(request, "Cannot delete a slot that already has a booking.")
                return redirect(request.path + f"?date={slot_start.date().isoformat()}")

            slot_date = slot_start.date()
            slot_time_start = slot_start.time()
            slot_time_end = slot_end.time()

            try:
                window = DoctorAvailability.objects.get(
                    doctor=doctor,
                    date=slot_date,
                    start_time__lte=slot_time_start,
                    end_time__gte=slot_time_end,
                )
            except DoctorAvailability.DoesNotExist:
                messages.error(request, "No matching availability window for this slot.")
                return redirect(request.path + f"?date={slot_date.isoformat()}")

            s = window.start_time
            e = window.end_time

            # 4 cases: remove [slot_time_start, slot_time_end) from [s, e)
            if s == slot_time_start and e == slot_time_end:
                # entire window is just this slot
                window.delete()
            elif s == slot_time_start and slot_time_end < e:
                # removing first slot; move start forward
                window.start_time = slot_time_end
                window.save()
            elif s < slot_time_start and slot_time_end == e:
                # removing last slot; move end backward
                window.end_time = slot_time_start
                window.save()
            else:
                # splitting the window into two
                # [s, slot_time_start) and [slot_time_end, e)
                DoctorAvailability.objects.create(
                    doctor=doctor,
                    date=slot_date,
                    start_time=slot_time_end,
                    end_time=e,
                )
                window.end_time = slot_time_start
                window.save()

            messages.success(request, "Slot removed from your availability.")
            return redirect(request.path + f"?date={slot_date.isoformat()}")

        # --- CREATE / UPDATE DAILY WINDOW ---
        else:
            date_str = request.POST.get("date")
            start_str = request.POST.get("start_time")
            end_str = request.POST.get("end_time")

            if not (date_str and start_str and end_str):
                messages.error(request, "Please select date, start time, and end time.")
                return redirect("doctor-schedule")

            try:
                d = datetime.strptime(date_str, "%Y-%m-%d").date()
                start_t = datetime.strptime(start_str, "%H:%M").time()
                end_t = datetime.strptime(end_str, "%H:%M").time()
            except ValueError:
                messages.error(request, "Invalid date or time.")
                return redirect("doctor-schedule")

            if start_t >= end_t:
                messages.error(request, "Start time must be before end time.")
                return redirect("doctor-schedule")

            obj, created = DoctorAvailability.objects.update_or_create(
                doctor=doctor,
                date=d,
                defaults={
                    "start_time": start_t,
                    "end_time": end_t,
                },
            )
            if created:
                messages.success(request, f"Availability created for {d}.")
            else:
                messages.success(request, f"Availability updated for {d}.")

            # After updating, show that day's slots immediately
            return redirect(request.path + f"?date={d.isoformat()}")

    # For GET (or after POST redirect):
    windows = DoctorAvailability.objects.filter(doctor=doctor).order_by("date", "start_time")

    available_slots = []
    if selected_date:
        available_slots = get_available_slots_for_doctor(doctor, selected_date)

    context = {
        "windows": windows,
        "selected_date": selected_date,
        "available_slots": available_slots,
    }
    return render(request, "core/doctor_schedule.html", context)
