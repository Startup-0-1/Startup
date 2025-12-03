from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User, PatientProfile, DoctorProfile, Document, Prescription, Payment, Appointment, DoctorAvailability


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Use Django's built-in UserAdmin behavior for our custom User."""

    ordering = ("email",)
    list_display = ("email", "role", "is_active", "is_staff", "is_superuser", "created_at")
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("email",)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Permissions"), {
            "fields": (
                "role",
                "is_active",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions",
            )
        }),
        (_("Important dates"), {"fields": ("last_login",)}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2", "role", "is_staff", "is_superuser"),
        }),
    )

    # We don't use username, so tell UserAdmin to treat email as the main id
    filter_horizontal = ("groups", "user_permissions")


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "user", "contact_number")
    search_fields = ("full_name", "user__email")


@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "specialization", "license_number")
    search_fields = ("full_name", "specialization", "license_number")

@admin.register(DoctorAvailability)
class DoctorAvailabilityAdmin(admin.ModelAdmin):
    list_display = ("doctor", "date", "start_time", "end_time", "created_at")
    list_filter = ("doctor", "date")
    search_fields = ("doctor__email",)

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("file_name", "document_type", "owner_user", "uploaded_by_user", "created_at")
    list_filter = ("document_type",)
    search_fields = ("file_name", "owner_user__email", "uploaded_by_user__email")


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ("title", "patient", "doctor", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("title", "patient__email", "doctor__email")

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("user", "amount_cents", "currency", "status", "created_at")
    list_filter = ("status", "currency")
    search_fields = ("user__email", "stripe_session_id", "description")

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("patient", "doctor", "scheduled_for", "status", "is_paid", "created_at")
    list_filter = ("status", "doctor", "patient")
    search_fields = ("patient__email", "doctor__email", "reason")
