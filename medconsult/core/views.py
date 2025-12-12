from datetime import datetime, date, time, timedelta
from functools import wraps

import stripe

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    login as auth_login,
    logout as auth_logout,
    update_session_auth_hash,
)
from django.contrib.auth.decorators import login_required
from django.http import (
    HttpResponseBadRequest,
    HttpResponseNotAllowed,
    HttpResponseForbidden,
)
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.db import IntegrityError

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    User,
    Payment,
    Appointment,
    DoctorAvailability,
    Document,
    Prescription,
)
from .serializers import (
    UserSerializer,
    PatientSignupSerializer,
    DoctorSignupSerializer,
    LoginSerializer,
)


# ==============================================================
#  STRIPE CONFIGURATION
# ==============================================================
stripe.api_key = settings.STRIPE_SECRET_KEY


# ==============================================================
#  ROLE-BASED ACCESS DECORATORS
# ==============================================================
def role_required(required_role):
    """
    Require a given role (patient/doctor/admin).
    Admins always bypass permissions.
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            user = request.user

            # Admin can access everything
            if getattr(user, "is_admin", False):
                return view_func(request, *args, **kwargs)

            # Normal role match
            if user.role == required_role:
                return view_func(request, *args, **kwargs)

            return HttpResponseForbidden("You do not have permission to access this resource.")
        return _wrapped
    return decorator


# ==============================================================
#  LOGOUT
# ==============================================================
@login_required
def logout_view(request):
    auth_logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("welcome")


# ==============================================================
#  DATA NORMALIZATION HELPERS
# ==============================================================
def normalize_dob_input(raw: str | None) -> str | None:
    """
    Normalize date-of-birth inputs to YYYY-MM-DD.
    Accepts:
        - 06/27/1992
        - 06-27-1992
        - 06271992
        - 1992-06-27
    """
    if not raw:
        return raw
    raw = raw.strip()
    digits = "".join(ch for ch in raw if ch.isdigit())

    # Interpret 06271992 as MMDDYYYY
    if len(digits) == 8:
        mm, dd, yyyy = digits[0:2], digits[2:4], digits[4:8]
        try:
            dt = datetime.strptime(f"{mm}/{dd}/{yyyy}", "%m/%d/%Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return raw

    # Try common formats
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    return raw


# ==============================================================
#  DOCTOR SLOT GENERATION
# ==============================================================
SLOT_MINUTES = 30
SLOT_DELTA = timedelta(minutes=SLOT_MINUTES)


def get_available_slots_for_doctor(doctor: User, target_date: date):
    """
    Return 30-minute slots that are:
        - Within DoctorAvailability windows
        - Not booked
        - In the future
    """
    windows = DoctorAvailability.objects.filter(
        doctor=doctor,
        date=target_date,
    ).order_by("start_time")

    if not windows.exists():
        return []

    tz = timezone.get_current_timezone()

    # Full-day range
    start_of_day = timezone.make_aware(datetime.combine(target_date, time(0, 0)), tz)
    end_of_day = timezone.make_aware(datetime.combine(target_date, time(23, 59, 59)), tz)

    # Booked slots (any status except cancelled/rejected/rescheduled)
    booked = set(
        Appointment.objects.filter(
            doctor=doctor,
            scheduled_for__gte=start_of_day,
            scheduled_for__lte=end_of_day,
        )
        .exclude(status__in=["cancelled", "rejected", "rescheduled"])
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

            if current_start > now and current_start not in booked:
                slots.append((current_start, current_end))

            current_start = current_end

    return slots


# ==============================================================
#  APPOINTMENT GROUPING HELPERS
# ==============================================================
def group_appointments_for_patient(qs):
    """
    Collapse contiguous 30-minute appointments into blocks.
    """
    qs = qs.order_by("doctor__id", "scheduled_for")
    blocks, current = [], None

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
                "rescheduled_from": appt.rescheduled_from,
            }
            continue

        last_start = current["slots"][-1].scheduled_for
        same_block = (
            appt.doctor_id == current["doctor"].id
            and appt.patient_id == current["patient"].id
            and day == current["date"]
            and appt.status == current["status"]
            and appt.reason == current["reason"]
            and appt.payment_id == (current["payment"].id if current["payment"] else None)
            and appt.scheduled_for == last_start + SLOT_DELTA
            and (appt.rescheduled_from_id or None)
            == (current["rescheduled_from"].id if current["rescheduled_from"] else None)
        )

        if same_block:
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
                "rescheduled_from": appt.rescheduled_from,
            }

    if current:
        blocks.append(current)

    return blocks


def group_appointments_for_doctor(qs):
    """
    Same grouping logic but keyed by patient.
    """
    qs = qs.order_by("patient__id", "scheduled_for")
    blocks, current = [], None

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
                "rescheduled_from": appt.rescheduled_from,
            }
            continue

        last_start = current["slots"][-1].scheduled_for
        same_block = (
            appt.doctor_id == current["doctor"].id
            and appt.patient_id == current["patient"].id
            and day == current["date"]
            and appt.status == current["status"]
            and appt.reason == current["reason"]
            and appt.payment_id == (current["payment"].id if current["payment"] else None)
            and appt.scheduled_for == last_start + SLOT_DELTA
            and (appt.rescheduled_from_id or None)
            == (current["rescheduled_from"].id if current["rescheduled_from"] else None)
        )

        if same_block:
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
                "rescheduled_from": appt.rescheduled_from,
            }

    if current:
        blocks.append(current)

    return blocks


# ==============================================================
#  HTML — AUTH / LANDING
# ==============================================================
def welcome_page(request):
    return render(request, "core/welcome.html")


def login_page(request):
    if request.method == "POST":
        email = request.POST.get("email")
        pw = request.POST.get("password")

        user = authenticate(request, username=email, password=pw)
        if user:
            auth_login(request, user)
            messages.success(request, f"Logged in as {user.email} ({user.role})")
            return redirect("welcome")

        messages.error(request, "Invalid email or password.")

    return render(request, "core/login.html")


@login_required
def timezone_settings_view(request):
    return redirect("settings-view")


# ==============================================================
#  SIGNUP VIEWS (HTML)
# ==============================================================
def patient_signup_page(request):
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

        for field, errs in serializer.errors.items():
            for err in errs:
                messages.error(request, f"{field}: {err}")

    return render(request, "core/signup_patient.html")


def doctor_signup_page(request):
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

        for field, errs in serializer.errors.items():
            for err in errs:
                messages.error(request, f"{field}: {err}")

    return render(request, "core/signup_doctor.html")


# ==============================================================
#  PATIENT APPOINTMENT VIEWS
# ==============================================================
@role_required("patient")
def patient_appointment_list(request):
    qs = Appointment.objects.filter(patient=request.user).order_by("scheduled_for")
    blocks = group_appointments_for_patient(qs)
    return render(
        request, "core/appointments_patient_list.html",
        {"appointment_blocks": blocks, "now": timezone.now()},
    )


@role_required("patient")
def patient_appointment_create(request):
    """
    Step 1: Choose doctor + date → see slots
    Step 2: POST → create 1+ appointment slots
    """
    doctors = User.objects.filter(role="doctor", is_active=True).order_by("email")

    doctor_param = request.GET.get("doctor_id")
    date_param = request.GET.get("date")

    selected_doctor = None
    selected_date = None
    available_slots = []

    # Step 1 — get requested doctor/date → show slots
    if doctor_param and date_param:
        try:
            selected_doctor = User.objects.get(id=doctor_param, role="doctor")
            selected_date = datetime.strptime(date_param, "%Y-%m-%d").date()
            available_slots = get_available_slots_for_doctor(selected_doctor, selected_date)
        except Exception:
            messages.error(request, "Invalid doctor or date selection.")

    # Step 2 — POST booking
    if request.method == "POST":
        doc_id = request.POST.get("doctor_id")
        date_str = request.POST.get("date")
        slot_starts = request.POST.getlist("slot_start")
        reason = request.POST.get("reason")

        if not doc_id or not date_str:
            messages.error(request, "Select doctor and date.")
            return redirect("patient-appointment-create")

        if not slot_starts:
            messages.error(request, "Select at least one time slot.")
            return redirect(f"{reverse('patient-appointment-create')}?doctor_id={doc_id}&date={date_str}")

        try:
            doctor = User.objects.get(id=doc_id, role="doctor")
            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            messages.error(request, "Invalid doctor or date.")
            return redirect("patient-appointment-create")

        created = 0
        tz = timezone.get_current_timezone()

        for slot_str in slot_starts:
            try:
                slot_naive = datetime.strptime(slot_str, "%Y-%m-%dT%H:%M")
                slot_start = timezone.make_aware(slot_naive, tz)
            except ValueError:
                continue

            if Appointment.objects.filter(doctor=doctor, scheduled_for=slot_start)\
                .exclude(status="cancelled").exists():
                continue

            Appointment.objects.create(
                patient=request.user,
                doctor=doctor,
                scheduled_for=slot_start,
                reason=reason,
                status="requested",
            )
            created += 1

        if created == 0:
            messages.error(request, "Selected slots unavailable.")
            return redirect(f"{reverse('patient-appointment-create')}?doctor_id={doctor.id}&date={date_str}")

        messages.success(request, f"Appointment requested for {created} slot(s).")
        return redirect("patient-appointments")

    return render(
        request, "core/appointments_patient_create.html",
        {"doctors": doctors, "selected_doctor": selected_doctor,
         "selected_date": selected_date, "available_slots": available_slots},
    )


@role_required("patient")
def patient_reschedule_block(request):
    """
    Reschedule a block of contiguous 30-minute appointments.
    """
    user = request.user

    doctor_id = request.GET.get("doctor_id") or request.POST.get("doctor_id")
    start_str = request.GET.get("start") or request.POST.get("start")
    end_str = request.GET.get("end") or request.POST.get("end")

    if not (doctor_id and start_str and end_str):
        messages.error(request, "Missing appointment information.")
        return redirect("patient-appointments")

    # Parse original block range
    tz = timezone.get_current_timezone()
    try:
        naive_start = datetime.strptime(start_str, "%Y-%m-%dT%H:%M")
        naive_end = datetime.strptime(end_str, "%Y-%m-%dT%H:%M")
        original_start = timezone.make_aware(naive_start, tz)
        original_end = timezone.make_aware(naive_end, tz)
    except ValueError:
        messages.error(request, "Invalid appointment time.")
        return redirect("patient-appointments")

    doctor = get_object_or_404(User, id=doctor_id, role="doctor")

    original_qs = Appointment.objects.filter(
        patient=user,
        doctor=doctor,
        scheduled_for__gte=original_start,
        scheduled_for__lt=original_end,
    ).exclude(status__in=["cancelled", "completed", "rescheduled"])\
     .order_by("scheduled_for")

    if not original_qs.exists():
        messages.error(request, "No active appointment block found.")
        return redirect("patient-appointments")

    now = timezone.now()
    if original_start <= now:
        messages.error(request, "Cannot reschedule past appointments.")
        return redirect("patient-appointments")

    selected_date_str = request.GET.get("new_date") or request.POST.get("new_date")
    selected_date = None
    available_slots = []

    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
            available_slots = get_available_slots_for_doctor(doctor, selected_date)
        except ValueError:
            pass

    # POST — finalize reschedule
    if request.method == "POST":
        new_date = request.POST.get("new_date")
        new_slot = request.POST.get("new_slot")

        if not (new_date and new_slot):
            messages.error(request, "Select new date and time.")
            return redirect(request.get_full_path())

        try:
            naive_new_start = datetime.strptime(new_slot, "%Y-%m-%dT%H:%M")
            new_start = timezone.make_aware(naive_new_start, tz)
        except ValueError:
            messages.error(request, "Invalid new slot.")
            return redirect("patient-appointments")

        if new_start <= now:
            messages.error(request, "Cannot reschedule to past.")
            return redirect("patient-appointments")

        conflict = Appointment.objects.filter(
            doctor=doctor,
            scheduled_for=new_start,
        ).exclude(status__in=["cancelled", "rejected", "rescheduled"]).exists()

        if conflict:
            messages.error(request, "Slot just taken. Pick another.")
            return redirect(request.get_full_path())

        original_root = original_qs.first()
        new_reason = original_root.reason

        Appointment.objects.create(
            patient=user,
            doctor=doctor,
            scheduled_for=new_start,
            reason=new_reason,
            status="reschedule_requested",
            rescheduled_from=original_root,
        )

        messages.success(request, "Your appointment has been rescheduled.")
        return redirect("patient-appointments")

    context = {
        "doctor": doctor,
        "original_start": original_start,
        "original_end": original_end,
        "original_block_appointments": original_qs,
        "selected_date": selected_date,
        "available_slots": available_slots,
        "doctor_id": doctor_id,
        "start_str": start_str,
        "end_str": end_str,
    }
    return render(request, "core/appointment_reschedule.html", context)


# ==============================================================
#  DOCTOR APPOINTMENT VIEWS
# ==============================================================
@role_required("doctor")
def doctor_appointment_list(request):
    qs = Appointment.objects.filter(doctor=request.user).order_by("scheduled_for")
    blocks = group_appointments_for_doctor(qs)

    for block in blocks:
        slot_ranges = []
        for appt in block["slots"]:
            slot_ranges.append({
                "id": appt.id,
                "start": appt.scheduled_for,
                "end": appt.scheduled_for + SLOT_DELTA,
            })
        block["slot_ranges"] = slot_ranges

    return render(
        request, "core/appointments_doctor_list.html",
        {"appointment_blocks": blocks},
    )


@role_required("doctor")
def doctor_update_appointments(request):
    """
    Doctor bulk updates:
        - approve/reject block
        - cancel slots
        - handle reschedules
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    mode = request.POST.get("mode")
    slot_ids = request.POST.getlist("slot_ids")

    if not slot_ids:
        messages.error(request, "No slots selected.")
        return redirect("doctor-appointments")

    appointments = list(
        Appointment.objects.filter(id__in=slot_ids, doctor=request.user)
        .order_by("scheduled_for")
    )
    if not appointments:
        messages.error(request, "No matching appointments.")
        return redirect("doctor-appointments")

    # --------------------------
    # SET STATUS MODE
    # --------------------------
    if mode == "set_status":
        new_status = request.POST.get("new_status")

        if new_status not in [
            "requested", "approved", "rejected",
            "completed", "cancelled", "reschedule_requested"
        ]:
            messages.error(request, "Invalid status.")
            return redirect("doctor-appointments")

        for appt in appointments:

            # CASE 1 — approving a rescheduled appointment
            if new_status == "approved" and appt.rescheduled_from:
                original = appt.rescheduled_from
                original.delete()
                appt.status = "approved"
                appt.save()
                continue

            # CASE 2 — rejecting/cancelling a rescheduled appointment
            if new_status in ["rejected", "cancelled"] and appt.rescheduled_from:
                appt.delete()
                continue

            # CASE 3 — normal
            appt.status = new_status
            appt.save()

        messages.success(request, f"Status updated to '{new_status}' for selected block.")
        return redirect("doctor-appointments")

    # --------------------------
    # CANCEL SLOTS MODE
    # --------------------------
    elif mode == "cancel_slots":
        count = 0
        for appt in appointments:
            if appt.status != "cancelled":
                appt.status = "cancelled"
                appt.save()
                count += 1

        if count == 0:
            messages.info(request, "No slots were cancelled.")
        else:
            messages.success(request, f"Cancelled {count} slot(s).")

        return redirect("doctor-appointments")

    else:
        messages.error(request, "Unknown action.")
        return redirect("doctor-appointments")


# ==============================================================
#  PAYMENT VIEWS
# ==============================================================
@role_required("patient")
def payment_page(request):
    amount_cents = 5000
    currency = "usd"

    return render(
        request, "core/payment.html",
        {"amount_dollars": amount_cents / 100, "currency": currency.upper()},
    )


@role_required("patient")
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
            line_items=[{
                "price_data": {
                    "currency": currency,
                    "product_data": {"name": "Consultation fee"},
                    "unit_amount": amount_cents,
                },
                "quantity": 1,
            }],
            customer_email=request.user.email,
            success_url=request.build_absolute_uri(reverse("payment-success"))
            + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=request.build_absolute_uri(reverse("payment-cancel")),
        )
    except Exception as e:
        payment.status = "failed"
        payment.save()
        return HttpResponseBadRequest(f"Stripe error: {e}")

    payment.stripe_session_id = session.id
    payment.save()

    return redirect(session.url)


@role_required("patient")
def payment_success(request):
    session_id = request.GET.get("session_id")
    if not session_id:
        return HttpResponseBadRequest("Missing session_id")

    try:
        session = stripe.checkout.Session.retrieve(session_id)
        payment = Payment.objects.get(stripe_session_id=session.id, user=request.user)
    except Exception:
        return HttpResponseBadRequest("Invalid session or payment missing")

    if session.payment_status == "paid":
        payment.status = "paid"
        payment.save()

    return render(
        request,
        "core/payment_success.html",
        {"payment": payment, "amount_dollars": payment.amount_cents / 100},
    )


@role_required("patient")
def payment_cancel(request):
    return render(request, "core/payment_cancel.html")


# ==============================================================
#  API (DRF) VIEWS
# ==============================================================
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


# ==============================================================
#  PROFILE VIEW (HTML)
# ==============================================================
@login_required
def profile_view(request):
    """
    User profile management:
        - Update email
        - Update patient/doctor fields
        - Change password
        - Upload profile image
    """
    user = request.user
    patient_profile = getattr(user, "patient_profile", None)
    doctor_profile = getattr(user, "doctor_profile", None)

    if request.method == "POST":
        action = request.POST.get("action")

        # ----------------------
        # Update profile fields
        # ----------------------
        if action == "update_profile":
            new_email = request.POST.get("email", "").strip()
            if new_email and new_email != user.email:
                if User.objects.filter(email=new_email).exclude(id=user.id).exists():
                    messages.error(request, "That email is already in use.")
                else:
                    user.email = new_email
                    user.save()
                    messages.success(request, "Email updated.")

            # Patient fields
            if patient_profile:
                patient_profile.full_name = request.POST.get("full_name", patient_profile.full_name)
                patient_profile.date_of_birth = request.POST.get("date_of_birth", patient_profile.date_of_birth)
                patient_profile.gender = request.POST.get("gender", patient_profile.gender)
                patient_profile.contact_number = request.POST.get("contact_number", patient_profile.contact_number)
                patient_profile.address = request.POST.get("address", patient_profile.address)
                patient_profile.emergency_contact = request.POST.get("emergency_contact", patient_profile.emergency_contact)
                patient_profile.insurance_provider = request.POST.get("insurance_provider", patient_profile.insurance_provider)
                patient_profile.insurance_policy_number = request.POST.get("insurance_policy_number", patient_profile.insurance_policy_number)
                patient_profile.save()

            # Doctor fields
            if doctor_profile:
                doctor_profile.full_name = request.POST.get("full_name", doctor_profile.full_name)
                doctor_profile.specialization = request.POST.get("specialization", doctor_profile.specialization)
                doctor_profile.contact_number = request.POST.get("contact_number", doctor_profile.contact_number)
                doctor_profile.clinic_name = request.POST.get("clinic_name", doctor_profile.clinic_name)
                doctor_profile.clinic_address = request.POST.get("clinic_address", doctor_profile.clinic_address)
                doctor_profile.save()

            messages.success(request, "Profile updated.")
            return redirect("profile")

        # ----------------------
        # Change password
        # ----------------------
        elif action == "change_password":
            current_pw = request.POST.get("current_password")
            new_pw1 = request.POST.get("new_password1")
            new_pw2 = request.POST.get("new_password2")

            if not user.check_password(current_pw):
                messages.error(request, "Current password is incorrect.")
            elif not new_pw1 or new_pw1 != new_pw2:
                messages.error(request, "New passwords do not match.")
            else:
                user.set_password(new_pw1)
                user.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Password changed successfully.")

            return redirect("profile")

        # ----------------------
        # Upload profile image
        # ----------------------
        elif action == "upload_image":
            img = request.FILES.get("profile_image")
            if not img:
                messages.error(request, "Please choose an image to upload.")
            else:
                user.profile_image = img
                user.save()
                messages.success(request, "Profile image updated.")
            return redirect("profile")

    return render(
        request,
        "core/profile.html",
        {
            "user_obj": user,
            "patient_profile": patient_profile,
            "doctor_profile": doctor_profile,
        },
    )


# ==============================================================
#  DOCUMENT VIEWS (UPLOAD + LIST)
# ==============================================================
@login_required
def documents_view(request):
    if request.method == "POST":
        uploaded = request.FILES.get("file")
        doc_type = request.POST.get("document_type", "other")
        file_name = request.POST.get("file_name") or (uploaded.name if uploaded else None)

        if not uploaded:
            messages.error(request, "Please choose a file.")
        else:
            Document.objects.create(
                owner_user=request.user,
                uploaded_by_user=request.user,
                uploader_role=request.user.role,
                file_name=file_name,
                file=uploaded,
                document_type=doc_type,
            )
            messages.success(request, "Document uploaded.")

        return redirect("documents")

    docs = Document.objects.filter(owner_user=request.user).order_by("-created_at")
    return render(request, "core/documents.html", {"documents": docs})


# ==============================================================
#  PRESCRIPTION VIEWS
# ==============================================================
@login_required
def prescriptions_view(request):
    user = request.user

    if getattr(user, "is_patient", False):
        prescriptions = Prescription.objects.filter(patient=user).order_by("-created_at")
    elif getattr(user, "is_doctor", False):
        prescriptions = Prescription.objects.filter(doctor=user).order_by("-created_at")
    elif getattr(user, "is_admin", False):
        prescriptions = Prescription.objects.all().order_by("-created_at")
    else:
        # Fallback: no prescriptions if some weird role sneaks in
        prescriptions = Prescription.objects.none()

    return render(request, "core/prescriptions.html", {"prescriptions": prescriptions})



# ==============================================================
#  SETTINGS VIEW (THEME / TIMEZONE / LOCATION)
# ==============================================================
@login_required
def settings_view(request):
    user = request.user

    if request.method == "POST":
        theme = request.POST.get("theme")
        timezone_name = request.POST.get("timezone")
        location_tracking = bool(request.POST.get("location_tracking"))

        if theme in ("light", "dark"):
            user.theme_preference = theme

        user.location_tracking_enabled = location_tracking

        if timezone_name:
            request.session["django_timezone"] = timezone_name
            timezone.activate(timezone_name)
        else:
            request.session.pop("django_timezone", None)
            timezone.deactivate()

        user.save()
        messages.success(request, "Settings updated.")
        return redirect("settings-view")

    context = {
        "current_theme": user.theme_preference or "light",
        "current_tz": request.session.get("django_timezone"),
        "location_tracking_enabled": user.location_tracking_enabled,
    }
    return render(request, "core/settings.html", context)


# ==============================================================
#  DOCTOR AVAILABILITY / SCHEDULE MANAGEMENT
# ==============================================================
@role_required("doctor")
def doctor_schedule_view(request):
    """
    Doctor sets availability windows per day.
    Patients see 30-minute slots generated from these windows.
    """
    doctor = request.user

    date_param = request.GET.get("date") or request.POST.get("selected_date")
    selected_date = None
    if date_param:
        try:
            selected_date = datetime.strptime(date_param, "%Y-%m-%d").date()
        except ValueError:
            selected_date = None

    # --------------------------
    # POST — DELETE SLOT
    # --------------------------
    if request.method == "POST" and request.POST.get("action") == "delete_slot":
        slot_str = request.POST.get("slot_start")
        if not slot_str:
            messages.error(request, "Missing slot to delete.")
            return redirect(request.get_full_path())

        try:
            naive_start = datetime.strptime(slot_str, "%Y-%m-%dT%H:%M")
        except ValueError:
            messages.error(request, "Invalid slot timestamp.")
            return redirect(request.get_full_path())

        tz = timezone.get_current_timezone()
        slot_start = timezone.make_aware(naive_start, tz)
        slot_end = slot_start + SLOT_DELTA

        if slot_start <= timezone.now():
            messages.error(request, "Cannot delete past slot.")
            return redirect(request.get_full_path())

        # Cannot delete booked slot
        if Appointment.objects.filter(
            doctor=doctor,
            scheduled_for=slot_start,
        ).exclude(status="cancelled").exists():
            messages.error(request, "Cannot delete a booked slot.")
            return redirect(request.get_full_path())

        slot_date = slot_start.date()
        try:
            window = DoctorAvailability.objects.get(
                doctor=doctor,
                date=slot_date,
                start_time__lte=slot_start.time(),
                end_time__gte=slot_end.time(),
            )
        except DoctorAvailability.DoesNotExist:
            messages.error(request, "No availability window for this slot.")
            return redirect(request.get_full_path())

        s, e = window.start_time, window.end_time

        # Remove slot from window (4 scenarios)
        if s == slot_start.time() and e == slot_end.time():
            window.delete()
        elif s == slot_start.time() and slot_end.time() < e:
            window.start_time = slot_end.time()
            window.save()
        elif s < slot_start.time() and slot_end.time() == e:
            window.end_time = slot_start.time()
            window.save()
        else:
            # Split window into two
            DoctorAvailability.objects.create(
                doctor=doctor,
                date=slot_date,
                start_time=slot_end.time(),
                end_time=e,
            )
            window.end_time = slot_start.time()
            window.save()

        messages.success(request, "Slot removed.")
        return redirect(request.get_full_path())

    # --------------------------
    # POST — CREATE/UPDATE WINDOW
    # --------------------------
    if request.method == "POST" and request.POST.get("action") != "delete_slot":
        date_str = request.POST.get("date")
        start_str = request.POST.get("start_time")
        end_str = request.POST.get("end_time")

        if not (date_str and start_str and end_str):
            messages.error(request, "Select date, start time, and end time.")
            return redirect("doctor-schedule")

        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
            start_t = datetime.strptime(start_str, "%H:%M").time()
            end_t = datetime.strptime(end_str, "%H:%M").time()
        except ValueError:
            messages.error(request, "Invalid date or time.")
            return redirect("doctor-schedule")

        if start_t >= end_t:
            messages.error(request, "Start must be before end.")
            return redirect("doctor-schedule")

        obj, created = DoctorAvailability.objects.update_or_create(
            doctor=doctor,
            date=d,
            defaults={"start_time": start_t, "end_time": end_t},
        )

        messages.success(request, f"Availability {'created' if created else 'updated'} for {d}.")
        return redirect(request.path + f"?date={d.isoformat()}")

    # --------------------------
    # GET (or post redirect): show windows + slots
    # --------------------------
    windows = DoctorAvailability.objects.filter(doctor=doctor).order_by("date", "start_time")
    available_slots = get_available_slots_for_doctor(doctor, selected_date) if selected_date else []

    return render(
        request, "core/doctor_schedule.html",
        {"windows": windows, "selected_date": selected_date, "available_slots": available_slots},
    )
