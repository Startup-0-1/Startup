# 🚀 MedConsult — Product Development Roadmap  
*A telemedicine platform in active development.*

This document outlines the full development plan for MedConsult, including what is already implemented and what needs to be completed in each phase. It serves as the canonical technical roadmap for the engineering team.

---

# ✅ Phase 1 — Core MVP (Already Implemented)

## 1. User System (Complete)
- Custom `User` model with roles: **patient**, **doctor**, **admin**.
- Separate `PatientProfile` and `DoctorProfile` models.
- Sign-up, login, logout (HTML + REST API).
- Basic profile editing (name, contact info, profile image).
- Settings page (partial).

## 2. Appointment Scheduling System (Complete)
- `DoctorAvailability` model to define available time windows.
- Automatic 30-minute slot generation.
- Patient appointment creation.
- Doctor approval / rejection workflow.
- Grouped time-block display for both doctors and patients.
- Appointment statuses: requested, approved, rejected, completed, cancelled.

## 3. Basic Stripe Payments (Complete)
- One-time Stripe Checkout session.
- Payment model tracking amount, currency, Stripe session ID, and status.
- Payment success/cancel views.

## 4. Document Upload System (Complete)
- Patients and doctors can upload documents.
- Categorized file uploads (lab report, prescription, ID, etc.).
- Document listing page per user.

## 5. Prescription Storage (Basic Version)
- Prescription model + file upload path.
- Prescription listing for doctor, patient, and admin.

---

# 🔥 Phase 2 — MVP Upgrade (High Priority Features)

## 6. Payment → Appointment Integration
- Tie Payment model to Appointment via foreign key.
- New appointment status: **Pending Payment**.
- Auto-confirm appointment only after successful Stripe payment.
- Display payment status in appointment detail.

## 7. Email Notifications
Implement emails for:
- account creation  
- appointment booking  
- doctor approval/rejection  
- payment success  
- document upload  
- prescription added  

SMTP or SendGrid recommended.

## 8. Appointment Rescheduling
- Patient requests a new timeslot.
- Doctor approves/denies reschedule request.
- Old appointment auto-cancelled or updated.

## 9. Timezone Support
- User-selectable timezone in settings.
- Normalize all datetime objects.
- Convert appointments to user's timezone.

---

# ⚡ Phase 3 — Communication Layer (Core Telemedicine Experience)

## 10. Real-Time Chat (Doctor ↔ Patient)
- `Message` model (sender, receiver, content, timestamp).
- Chat list view + chat detail UI.
- Real-time updates using Django Channels or polling.
- Message read receipts (optional).

## 11. Video Consultation Integration
- Generate secure call links (Zoom / Jitsi / Twilio).
- Attach meeting link to approved appointment.
- Add “Join Call” button for doctor and patient.
- Call duration tracking (optional).

---

# 🩺 Phase 4 — Medical & Compliance Features

## 12. Prescription PDF Generator
- Doctor fills structured form.
- Auto-generated PDF (via ReportLab or WeasyPrint).
- Stored under `prescriptions/<id>.pdf`.
- “Download Prescription” button.

## 13. Unified Medical History Timeline
Combine into a single chronological stream:
- appointments  
- documents  
- prescriptions  
- payments  

Displayed in a timeline UI with filtering.

## 14. Two-Factor Authentication (2FA)
- Email or app-based OTP.
- Backup codes for emergency login.

## 15. Audit Logging
Track sensitive actions:
- logins  
- profile edits  
- appointment changes  
- prescription updates  
- document uploads  

Stored in an `AuditLog` model.

## 16. Encrypted Document Storage
- Switch to encrypted storage backend or encrypted S3 bucket.
- Signed expiration URLs for file access.

---

# 📈 Phase 5 — Growth Features (Competitive Differentiators)

## 17. Subscription Plans
- Monthly/annual telehealth subscription tiers.
- Stripe Billing integration (recurring payments).
- Subscription status controls access to consultation features.

## 18. Doctor Ratings & Reviews
- Rating model (stars + comments).
- Patients review doctor after completed appointment.
- Doctor profile displays average rating.

## 19. Automated Reminders
- Email or SMS reminders for:
  - upcoming appointments  
  - prescription refills  
  - medication schedules  
- Cron/Celery scheduler required.

## 20. Admin Analytics Dashboard
- Appointment volume charts.
- Revenue metrics.
- Doctor performance analytics.
- User activity insights.

---

# 🤖 Phase 6 — AI Extensions (Optional but Highly Valuable)

## 21. AI Symptom Checker
- Patient enters symptoms → LLM or classifier predicts possible conditions.
- Provide recommended next steps (not medical advice).

## 22. AI Document Intelligence
- Extract text from uploads (OCR).
- Auto-summarize lab results or reports.
- Highlight critical values or trends.

## 23. AI Assistant for Doctors
- Auto-generate draft prescriptions.
- Auto-generate visit summaries.
- Suggest follow-up steps based on chat/notes.

---

# 🏛️ Phase 7 — Interoperability & Regulatory Alignment

## 24. FHIR-Style Health Records API
Expose structured health data via:
- Patients endpoint  
- Prescriptions endpoint  
- Appointments endpoint  
- Document metadata endpoint  

Enable interoperability with clinics and EHR systems.

---

# 🧱 Phase 8 — Engineering & Infrastructure

## 25. Dockerization
- Dockerfile for Django app.
- docker-compose (Django + Redis + Postgres + Nginx).
- Local and production parity.

## 26. Production Deployment
- Deploy to AWS / DigitalOcean / Render.
- Setup HTTPS (Let’s Encrypt).
- Optimize static/media file pipeline.

## 27. Security & Performance Improvements
- JWT for API authentication.
- CORS hardening.
- Rate limiting.
- Password strength policies.
- At-rest + in-transit encryption.

---

# 📌 Notes
- This roadmap is iterative.  
- Each phase should be developed in branches and merged via PR with testing.  
- Features labeled **high priority** directly improve user adoption and investor appeal.

---

# 🎯 Final Milestones Summary

| Phase | Milestone | Status |
|-------|-----------|--------|
| 1 | Core MVP | ✅ Done |
| 2 | MVP Upgrade | 🔥 High Priority |
| 3 | Communication Layer | 🔥 High Priority |
| 4 | Medical + Compliance | 🔶 Important |
| 5 | Growth Features | Medium Priority |
| 6 | AI Extensions | Optional |
| 7 | FHIR Interoperability | Advanced |
| 8 | Deployment & Security | Required for launch |

---

# 🚀 End of Roadmap  
MedConsult now has a clear roadmap that matches real startup expectations and your current implementation progress.
