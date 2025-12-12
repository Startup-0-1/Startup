from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from core import views


urlpatterns = [
    # ==========================================================
    # ADMIN
    # ==========================================================
    path(
        "admin/logout/",
        auth_views.LogoutView.as_view(next_page="welcome"),
        name="admin-logout",
    ),
    path("admin/", admin.site.urls),

    # ==========================================================
    # PUBLIC / AUTH
    # ==========================================================
    path("", views.welcome_page, name="welcome"),
    path("login/", views.login_page, name="login-page"),
    path("logout/", views.logout_view, name="logout-view"),

    path(
        "signup/patient/",
        views.patient_signup_page,
        name="signup-patient-page",
    ),
    path(
        "signup/doctor/",
        views.doctor_signup_page,
        name="signup-doctor-page",
    ),

    # ==========================================================
    # PATIENT APPOINTMENTS
    # ==========================================================
    path(
        "appointments/",
        views.patient_appointment_list,
        name="patient-appointments",
    ),
    path(
        "appointments/new/",
        views.patient_appointment_create,
        name="patient-appointment-create",
    ),
    path(
        "patient/appointments/reschedule/",
        views.patient_reschedule_block,
        name="patient-appointment-reschedule",
    ),

    # ==========================================================
    # DOCTOR APPOINTMENTS & SCHEDULE
    # ==========================================================
    path(
        "doctor/appointments/",
        views.doctor_appointment_list,
        name="doctor-appointments",
    ),
    path(
        "doctor/appointments/update/",
        views.doctor_update_appointments,
        name="doctor-update-appointments",
    ),
    path(
        "doctor/schedule/",
        views.doctor_schedule_view,
        name="doctor-schedule",
    ),

    # ==========================================================
    # PAYMENTS
    # ==========================================================
    path(
        "payments/",
        views.payment_page,
        name="payment-page",
    ),
    path(
        "payments/create-checkout-session/",
        views.create_checkout_session,
        name="create-checkout-session",
    ),
    path(
        "payments/success/",
        views.payment_success,
        name="payment-success",
    ),
    path(
        "payments/cancel/",
        views.payment_cancel,
        name="payment-cancel",
    ),

    # ==========================================================
    # PROFILE / DOCUMENTS / SETTINGS / PRESCRIPTIONS
    # ==========================================================
    path("profile/", views.profile_view, name="profile"),
    path("documents/", views.documents_view, name="documents"),
    path("prescriptions/", views.prescriptions_view, name="prescriptions"),

    path("settings/", views.settings_view, name="settings-view"),
    path(
        "settings/timezone/",
        views.timezone_settings_view,
        name="timezone-settings",
    ),

    # ==========================================================
    # API ENDPOINTS (DRF)
    # ==========================================================
    path(
        "api/patient/signup/",
        views.PatientSignupView.as_view(),
        name="api-patient-signup",
    ),
    path(
        "api/doctor/signup/",
        views.DoctorSignupView.as_view(),
        name="api-doctor-signup",
    ),
    path(
        "api/login/",
        views.LoginView.as_view(),
        name="api-login",
    ),
    path(
        "api/me/",
        views.MeView.as_view(),
        name="api-me",
    ),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
