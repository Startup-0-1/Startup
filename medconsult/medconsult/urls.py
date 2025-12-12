from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from core import views



urlpatterns = [
    path("admin/", admin.site.urls),

    # Landing / auth
    path("", views.welcome_page, name="welcome"),
    path("login/", views.login_page, name="login-page"),
    path("logout/", views.logout_view, name="logout-view"),

    # Signup (HTML)
    path("signup/patient/", views.patient_signup_page, name="signup-patient-page"),
    path("signup/doctor/", views.doctor_signup_page, name="signup-doctor-page"),

    # Profiles / documents / settings
    path("profile/", views.profile_view, name="profile"),
    path("documents/", views.documents_view, name="documents"),
    path("prescriptions/", views.prescriptions_view, name="prescriptions"),
    path("settings/", views.settings_view, name="settings-view"),

    # Patient appointments
    path("patient/appointments/", views.patient_appointment_list, name="patient-appointments"),
    path("patient/appointments/new/", views.patient_appointment_create, name="patient-appointment-create"),
    path("patient/appointments/reschedule/", views.patient_reschedule_block, name="patient-appointment-reschedule"),

    # Doctor appointments
    path("doctor/appointments/", views.doctor_appointment_list, name="doctor-appointments"),
    path("doctor/appointments/update/", views.doctor_update_appointments, name="doctor-appointments-update"),
    path("doctor/schedule/", views.doctor_schedule_view, name="doctor-schedule"),

    # Payments
    path("payment/", views.payment_page, name="payment-page"),
    path("payment/create-checkout-session/", views.create_checkout_session, name="create-checkout-session"),
    path("payment/success/", views.payment_success, name="payment-success"),
    path("payment/cancel/", views.payment_cancel, name="payment-cancel"),

    # API (DRF)
    path("api/signup/patient/", views.PatientSignupView.as_view(), name="api-patient-signup"),
    path("api/signup/doctor/", views.DoctorSignupView.as_view(), name="api-doctor-signup"),
    path("api/login/", views.LoginView.as_view(), name="api-login"),
    path("api/me/", views.MeView.as_view(), name="api-me"),

    # 🔍 Step 4 — Doctor search & detail
    path("doctors/", views.doctor_search_view, name="doctor-search"),
    path("doctors/<uuid:doctor_id>/", views.doctor_detail_view, name="doctor-detail"),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
