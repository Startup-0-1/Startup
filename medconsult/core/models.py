from datetime import time 
import uuid

from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    BaseUserManager,
)
from django.db import models
from django.core.exceptions import ValidationError 


# ==========================
# USER & AUTH MODELS
# ==========================


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, role="patient", **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")

        email = self.normalize_email(email)
        user = self.model(email=email, role=role, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", "admin")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ("patient", "Patient"),
        ("doctor", "Doctor"),
        ("admin", "Admin"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    profile_image = models.ImageField(
        upload_to="profile_images/",
        blank=True,
        null=True,
    )
    theme_preference = models.CharField(
        max_length=10,
        choices=(("light", "Light"), ("dark", "Dark")),
        default="light",
    )
    location_tracking_enabled = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def get_display_name(self):
        """
        Return a human-friendly display name for this user:
        - patient → PatientProfile.full_name
        - doctor → DoctorProfile.full_name
        - fallback → user.email
        """
        # Try patient profile
        for attr in ("patient_profile", "patientprofile"):
            profile = getattr(self, attr, None)
            if profile and getattr(profile, "full_name", None):
                return profile.full_name

        # Try doctor profile
        for attr in ("doctor_profile", "doctorprofile"):
            profile = getattr(self, attr, None)
            if profile and getattr(profile, "full_name", None):
                return profile.full_name

        return self.email

    def __str__(self):
        return f"{self.email} ({self.role})"

    @property   
    def is_patient(self):
        return self.role == "patient"

    @property
    def is_doctor(self):
        return self.role == "doctor"

    @property
    def is_admin(self):
        return self.role == "admin"


# ==========================
# PROFILE MODELS
# ==========================


class PatientProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="patient_profile",
    )
    full_name = models.CharField(max_length=255)
    date_of_birth = models.CharField(max_length=50)  # kept as text for now
    gender = models.CharField(max_length=50)
    contact_number = models.CharField(max_length=50)
    address = models.TextField()
    emergency_contact = models.CharField(max_length=255, blank=True, null=True)
    insurance_provider = models.CharField(max_length=255, blank=True, null=True)
    insurance_policy_number = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )
    
    def clean(self):
        super().clean()
        if self.user.role != "patient":
            raise ValidationError("PatientProfile.user must have role='patient'.")
        
    def __str__(self):
        return f"PatientProfile({self.full_name})"


class DoctorProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="doctor_profile",
    )
    full_name = models.CharField(max_length=255)
    specialization = models.CharField(max_length=255)
    license_number = models.CharField(max_length=255)
    years_of_experience = models.IntegerField()
    contact_number = models.CharField(max_length=50)
    clinic_name = models.CharField(max_length=255, blank=True, null=True)
    clinic_address = models.TextField(blank=True, null=True)
    bio = models.TextField(blank=True, null=True)

    def clean(self):
        super().clean()
        if self.user.role != "doctor":
            raise ValidationError("DoctorProfile.user must have role='doctor'.")
        
    def __str__(self):
        return f"DoctorProfile({self.full_name}, {self.specialization})"


# ==========================
# DOCUMENTS & PRESCRIPTIONS
# ==========================


def document_upload_path(instance, filename):
    """
    Store documents under:
    documents/<owner_user_id>/<uuid>_<filename>
    """
    return f"documents/{instance.owner_user.id}/{uuid.uuid4()}_{filename}"


def prescription_upload_path(instance, filename):
    """
    Store prescription files under:
    prescriptions/<patient_id>/<uuid>_<filename>
    """
    return f"prescriptions/{instance.patient.id}/{uuid.uuid4()}_{filename}"


class Document(models.Model):
    DOCUMENT_TYPE_CHOICES = (
        ("lab_report", "Lab Report"),
        ("id_proof", "ID Proof"),
        ("scan", "Scan"),
        ("prescription", "Prescription"),
        ("other", "Other"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="documents_owned",
    )
    uploaded_by_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="documents_uploaded",
    )
    uploader_role = models.CharField(
        max_length=20,
        choices=(
            ("patient", "Patient"),
            ("doctor", "Doctor"),
            ("admin", "Admin"),
        ),
    )
    file_name = models.CharField(max_length=255)
    file = models.FileField(upload_to=document_upload_path)
    document_type = models.CharField(
        max_length=50,
        choices=DOCUMENT_TYPE_CHOICES,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Document({self.file_name}, {self.document_type})"


class Prescription(models.Model):
    STATUS_CHOICES = (
        ("active", "Active"),
        ("completed", "Completed"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="prescriptions_patient",
    )
    doctor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="prescriptions_doctor",
    )
    title = models.CharField(max_length=255)
    notes = models.TextField()
    file = models.FileField(
        upload_to=prescription_upload_path,
        blank=True,
        null=True,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Prescription({self.title})"


# ==========================
# PAYMENTS
# ==========================


class Payment(models.Model):
    STATUS_CHOICES = (
        ("created", "Created"),
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    amount_cents = models.IntegerField()  # store in cents (e.g. 5000 = $50.00)
    currency = models.CharField(max_length=10, default="usd")
    stripe_session_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="created",
    )
    description = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        amount = self.amount_cents / 100 if self.amount_cents is not None else 0
        return f"Payment({self.user.email}, {amount:.2f} {self.currency}, {self.status})"


# ==========================
# APPOINTMENTS & AVAILABILITY
# ==========================


class Appointment(models.Model):
    STATUS_CHOICES = (
        ("requested", "Requested"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("reschedule_requested", "Reschedule Requested"),
        ("rescheduled", "Rescheduled"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="patient_appointments",
        limit_choices_to={"role": "patient"},
    )
    doctor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="doctor_appointments",
        limit_choices_to={"role": "doctor"},
    )
    rescheduled_from = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reschedules",
        help_text="If this appointment is a reschedule, link to the original one.",
    )
    scheduled_for = models.DateTimeField()
    reason = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="requested",
    )
    payment = models.ForeignKey(
        "Payment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["doctor", "scheduled_for"],
                name="unique_doctor_timeslot",
            )
        ]

    def __str__(self):
        return (
            f"Appointment({self.patient.email} → "
            f"{self.doctor.email} @ {self.scheduled_for} [{self.status}])"
        )

    @property
    def is_paid(self):
        return self.payment is not None and self.payment.status == "paid"


class DoctorAvailability(models.Model):
    """
    A simple availability window for a doctor on a specific date.
    Example: Jan 5, 2026 from 09:00 to 10:00.
    We will turn this into 30-minute slots on the patient side.
    """

    doctor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="availability_windows",
        limit_choices_to={"role": "doctor"},
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["doctor", "date", "start_time"]
        verbose_name_plural = "Doctor availability"

    def __str__(self):
        return f"{self.doctor.email} {self.date} {self.start_time}-{self.end_time}"
