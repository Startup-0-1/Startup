# Guide.md — MedConsult Path A (Django + Tailwind + HTMX) with a Path B Exit Ramp

**Goal (60 days):** a clean, modern, fully working platform (Doctor/Patient/Admin) that’s fast, secure-by-design, and already structured to evolve into **Path B** (DRF API + Next.js) without a rewrite.

**Non‑negotiables (we keep these because they help later):**

* **Service layer** (business logic outside views)
* **API-ready boundaries** (HTML + JSON from same core functions)
* **Postgres** (prod data), **S3-compatible storage** for media
* **Background jobs** (email/SMS, Stripe webhooks, reminders)
* **Audit logging** (who did what, when)
* **Role-based permissions** (Doctor/Patient/Admin, plus verified/unverified)
* **Test baseline + CI** (so refactors don’t break the app)

---

## 0) North Star Architecture

### Path A now

* Django (monolith)
* Server-rendered templates
* Tailwind CSS for styling
* HTMX for interactive UI without SPA
* Alpine.js only for tiny interactions (modals/tabs)

### Exit ramp to Path B later

* Add DRF endpoints gradually
* Keep the same service layer + serializers
* Next.js consumes DRF when you’re ready

**Core principle:** UI can change. API can grow. **Models + services stay stable.**

---

## 1) Project Re-Org (do this first)

### 1.1 Create these Django apps (if not already)

* `accounts/` (auth, user, profiles, verification states)
* `scheduling/` (availability, slots, appointments)
* `billing/` (Stripe, payments, invoices, refunds)
* `records/` (documents, prescriptions, visit notes)
* `integrations/` (future NHS and other providers)
* `audit/` (audit log entries)
* `ui/` (template components + static assets)

**Rule:** Views should be thin. Business rules live in `services.py` inside each app.

### 1.2 Add a service layer pattern

For every app:

* `services.py` (pure business actions)
* `selectors.py` (read-only queries)
* `validators.py` (shared validation)
* `api.py` (future DRF endpoints or shared serializers)

Example actions:

* `scheduling.services.book_appointment(...)`
* `billing.services.create_checkout_session(...)`
* `accounts.services.verify_doctor(...)`

### 1.3 Settings split

Create:

* `settings/base.py`
* `settings/dev.py`
* `settings/prod.py`

Move secrets to environment variables.

---

## 2) UI/UX Redesign (Path A, but professional)

### 2.1 Design system

* Tailwind (base)
* Component library approach (your own components)

Create reusable template components in `ui/templates/ui/components/`:

* `button.html` (primary/secondary/danger)
* `input.html` (with errors)
* `card.html`
* `badge.html` (appointment/payment statuses)
* `modal.html`
* `table.html`
* `empty_state.html`
* `toast.html`

**Rule:** No page-specific CSS. Everything is components + Tailwind utilities.

### 2.2 Layouts

Create base layouts:

* `ui/templates/ui/layout_public.html`
* `ui/templates/ui/layout_app.html` (dashboard layout with sidebar)

### 2.3 UX flows (mandatory)

* Patient: signup → complete profile → find doctor → pick slot → pay (if required) → confirmed → docs/prescriptions
* Doctor: signup → submit verification → set availability → manage appointments → upload docs/prescriptions
* Admin: verify doctors → manage disputes → oversee payments → audit logs

### 2.4 HTMX interaction plan

Use HTMX for:

* Live doctor search filters + pagination
* Slot availability fetch + booking without page reload
* Appointment approve/reject/reschedule actions
* Upload documents and refresh list
* Admin verify/reject doctor without full page refresh

Alpine.js only for:

* modal open/close
* tabs (profile sections)
* dropdown menus

---

## 3) Data + Performance Foundations

### 3.1 Database

* Dev: SQLite is fine
* Prod: Postgres (required)

Add indexes:

* Appointments: `(doctor_id, start_time)`, `(patient_id, start_time)`, `status`
* Availability: `(doctor_id, day_of_week)` and/or `(doctor_id, start_time)`

### 3.2 Media storage

* Dev: local `MEDIA_ROOT`
* Prod: S3-compatible (AWS S3, DigitalOcean Spaces, etc.)

### 3.3 Caching

* Redis (for sessions and caching slot computations)

---

## 4) Security & Compliance Foundations

### 4.1 Authentication

* Keep Django auth (Path A)
* Add **2FA optional** later (recommended)

### 4.2 Authorization

Implement explicit permission checks:

* role-based (patient/doctor/admin)
* object-based (can only view your own appointment, docs)
* verification-based (unverified doctors cannot appear in search or accept appointments)

### 4.3 Audit logging (non-negotiable)

Log events:

* doctor verification actions
* appointment status changes
* prescription creation/edit
* payment events

### 4.4 Security headers

* CSRF, secure cookies
* HSTS, CSP (production)
* strict session settings

---

## 5) Feature Upgrades (what you’ll add beyond current MVP)

### 5.1 Doctor verification workflow (Admin)

States:

* `PENDING` → `VERIFIED` / `REJECTED`

Admin tools:

* verify/reject + notes
* timeline of changes

### 5.2 Scheduling hardening (no double booking)

* Slot generation must consider existing appointments
* Booking must be **transactional** (atomic)
* Use DB constraints where possible

### 5.3 Payments (Stripe) completed properly

* Checkout session creation
* Stripe **webhooks** (source of truth)
* Payment ↔ appointment state machine
* Refund flow

### 5.4 Communications

* Email notifications (booking confirmed, rescheduled, cancelled)
* Optional SMS later

### 5.5 Records

* Visit notes
* Document categories + permissions
* Prescription lifecycle

---

## 6) NHS Integration Readiness (future-proof now)

### 6.1 Keep integrations isolated

All external provider logic goes into:

* `integrations/nhs/`

No direct NHS calls inside views.

### 6.2 Identity strategy

Prepare for OIDC providers:

* `integrations.oidc` helpers
* token storage + refresh patterns

### 6.3 Data minimization

Store:

* provider subject ID
* verification result
* timestamps

Avoid storing unnecessary identity data.

### 6.4 Auditability

Every external verification action writes to `audit/`.

---

## 7) Testing + Quality Gates

Minimum test suite:

* model tests (appointment constraints)
* service tests (book/reschedule/cancel)
* billing tests (webhook handling)

Add CI:

* run tests
* lint (ruff/black)

---

## 8) Deployment (so you can actually run this)

* Dockerize (app + Postgres + Redis)
* Gunicorn + Nginx
* Static files: collectstatic
* Media: S3
* Secrets: env vars

Observability:

* structured logging
* error tracking (Sentry recommended)

---

# 60-Day Step-by-Step Plan

## Week 1 (Days 1–7): Foundations + UI system

1. Create settings split (base/dev/prod)
2. Add Postgres locally (docker compose)
3. Add Tailwind build pipeline
4. Create UI component templates + base layouts
5. Move business logic out of views into services/selectors

**Deliverable:** App still works, UI skeleton + clean structure.

## Week 2 (Days 8–14): Roles, permissions, dashboards

1. Enforce role-based access checks everywhere
2. Build dashboards:

   * Patient dashboard
   * Doctor dashboard
   * Admin dashboard
3. Add audit logging model + middleware/hooks

**Deliverable:** Role-based UX feels real.

## Week 3 (Days 15–21): Scheduling v2 (reliable)

1. Implement transactional booking
2. Prevent double-booking
3. HTMX slot picker
4. Reschedule/cancel rules

**Deliverable:** Scheduling you can trust.

## Week 4 (Days 22–28): Doctor verification + Admin controls

1. Verification workflow + UI
2. Admin verification queue + filters
3. Block unverified doctors from being searchable/bookable

**Deliverable:** Trust layer implemented.

## Week 5 (Days 29–35): Payments completed

1. Stripe checkout cleaned up
2. Add Stripe webhooks
3. Appointment/payment state machine
4. Refund handling (basic)

**Deliverable:** Payments are real, not vibes.

## Week 6 (Days 36–42): Records + documents + prescriptions polish

1. Document categories + permissions
2. Prescriptions lifecycle
3. Add visit notes
4. Improve UI for records (cards, filters)

**Deliverable:** Clinical artifacts usable.

## Week 7 (Days 43–49): Notifications + background jobs

1. Add Redis + background worker (Celery or RQ)
2. Email notifications for key events
3. Appointment reminders

**Deliverable:** Platform starts acting like a platform.

## Week 8–9 (Days 50–60): API exit ramp + deployment hardening

1. Add DRF incrementally:

   * `/api/me/`
   * `/api/doctors/`
   * `/api/appointments/`
2. Ensure HTML and API share services/selectors
3. Docker + production checklist
4. Basic test coverage + CI

**Deliverable:** You can run it reliably and you’ve started Path B without rewriting.

---

# Execution Rules (so we don’t drown)

1. We do **one step at a time**.
2. Every step ends with a **working app**.
3. No feature gets implemented twice.
4. If it helps the exit ramp or improves UX/performance/security, it stays.

---

