# Guide.md

## Goal

In the next **60 days**, ship a **fully working MedConsult platform** using **Path A** (Django templates + Tailwind + HTMX) with a clean **exit ramp to Path B** (API-first / DRF + future Next.js) and a future-ready structure for **NHS-style integrations** and security requirements.

This guide is written to be followed **one step at a time**. Each step ends with a **Definition of Done** so you can confirm progress without vibes.

---

## North Star Deliverable (Day 60)

A production-ready MVP with:

* Role-based access (Admin / Doctor / Patient)
* Doctor onboarding + verification workflow
* Doctor search + filters + availability calendar
* Appointment booking + reschedule/cancel + conflict-free scheduling
* Payments (Stripe) with webhooks, refunds/cancellations policy hooks
* Documents (upload, access control, audit trail)
* Prescriptions (structured, downloadable, tied to appointment)
* Dashboards for each role
* Email notifications (appointment status, receipts, verification)
* Security baseline (CSRF, sessions, permissions, audit logging, secrets management)
* Observability (logging + error tracking) and deployment hygiene

**Exit ramp built-in:** service layer + JSON endpoints for key workflows so adding DRF + Next.js later is additive, not a rewrite.

---

## Core Principles (so we don’t paint ourselves into a corner)

1. **Thin views, fat services.** Views only parse input and return responses. Business logic lives in `services/`.
2. **State machines over spaghetti.** Appointments/Payments/Verification are explicit states.
3. **HTMX for interaction, not for chaos.** HTMX endpoints return partials; core actions still call services.
4. **Integration boundaries.** Any external system (NHS-like, insurance, SMS, email, Stripe) lives behind an `integrations/` interface.
5. **Data minimization.** Store only what you need; keep a clean audit trail.

---

## Project Structure Target (end-state)

Create these folders/apps (incrementally):

* `core/` (existing): core models, auth, base templates
* `appointments/` (new or refactor): booking/reschedule/cancel, slot logic
* `payments/` (new or refactor): Stripe checkout + webhooks + Payment state machine
* `documents/` (new or refactor): uploads + access + audit
* `prescriptions/` (new or refactor): RX generation + templates
* `dashboards/` (new): role dashboards
* `integrations/` (new):

  * `integrations/stripe/`
  * `integrations/email/`
  * `integrations/nhs/` (placeholder interface now)
* `services/` (new, project-level or per-app): business logic
* `ui/` (new, optional): template components + HTMX partials

If you don’t want new Django apps yet, we can still create `services/` and `integrations/` immediately and migrate logic gradually.

---

## 60-Day Plan (Step-by-step, one-by-one)

### Step 1 (Days 1–3): Baseline + Repo Hygiene

**Objective:** Make the project safe to iterate on quickly.

Tasks:

* Add/confirm `.env` usage for secrets (SECRET_KEY, STRIPE keys, email creds)
* Split settings: `settings/base.py`, `settings/dev.py`, `settings/prod.py`
* Update `.gitignore` to exclude `db.sqlite3`, `media/`, `__pycache__`, local env files
* Add `pre-commit` hooks (format + lint) (optional but recommended)
* Add a “Project Health” management command (`python manage.py check --deploy` for prod)

Definition of Done:

* App runs in dev with `.env`.
* Secrets are not hardcoded.
* `db.sqlite3` and `media/` are no longer required to be committed.

---

### Step 2 (Days 4–7): UI Foundation (Tailwind + Component Templates)

**Objective:** Make the UI consistent and modern without rewriting logic.

Tasks:

* Install Tailwind (Django-friendly build approach)
* Create a base design system:

  * typography scale
  * spacing rules
  * buttons, inputs, cards, badges
* Create template components:

  * `components/button.html`
  * `components/input.html`
  * `components/card.html`
  * `components/badge.html`
  * `components/modal.html`
* Rebuild base layout:

  * top nav + role-aware sidebar for authenticated pages
  * clean public layout for marketing/login

Definition of Done:

* 5–8 reusable components exist.
* Core pages inherit from a single clean base.

---

### Step 3 (Days 8–12): Service Layer + Permissions Cleanup

**Objective:** Create the exit ramp to Path B.

Tasks:

* Introduce `services/` (or per-app services) and move business logic out of views
* Define permission helpers (role checks, object ownership)
* Add consistent error handling and messages

Definition of Done:

* At least 3 key workflows use services:

  * book appointment
  * approve/reject
  * upload document

---

### Step 4 (Days 13–18): Scheduling That Doesn’t Lie (Conflict-Free)

**Objective:** No double booking, consistent slots, timezone correctness.

Tasks:

* Normalize timezone handling (doctor timezone vs patient timezone)
* Implement slot generation service
* Implement booking with conflict protection:

  * DB constraints where possible
  * transaction-based locking strategy
* Add reschedule rules and cancellation policy hooks

Definition of Done:

* Two users cannot book the same slot.
* Reschedule/cancel works and is consistent.

---

### Step 5 (Days 19–24): Doctor Verification Workflow (Trust Layer)

**Objective:** Introduce verification states + admin review.

Tasks:

* Add `DoctorVerification` model (or fields) with states:

  * PENDING, VERIFIED, REJECTED
* Admin verification queue UI
* Gate discovery + booking behind VERIFIED
* Store minimal verification metadata
* Add audit log entries

Definition of Done:

* Unverified doctors cannot appear in search or accept appointments.
* Admin can approve/reject with notes.

---

### Step 6 (Days 25–31): Search + Filters + Discovery UX

**Objective:** A “real product” search experience.

Tasks:

* Add filters: specialization, availability date, rating placeholder, location (if available)
* Pagination + sorting
* HTMX-powered filter updates

Definition of Done:

* Search feels fast, modern, and useful.

---

### Step 7 (Days 32–38): Payments That Close the Loop (Stripe Webhooks)

**Objective:** Payments become the source of truth, not vibes.

Tasks:

* Checkout session flow
* Webhooks for:

  * payment succeeded/failed
  * refunds
* Payment → Appointment coupling (paid = confirmed)
* Receipts/invoices basics

Definition of Done:

* Webhooks update Payment/Appointment status.
* You can trace one payment end-to-end.

---

### Step 8 (Days 39–45): Documents + Prescriptions + Access Control

**Objective:** Add real clinical artifact handling with permissions and audit.

Tasks:

* Documents:

  * upload, list, download
  * role-based access
  * audit logging
* Prescriptions:

  * structured fields
  * generate PDF/printable
  * tied to appointment

Definition of Done:

* Only authorized users can access documents.
* Prescription creation works and is downloadable.

---

### Step 9 (Days 46–52): Dashboards + Notifications

**Objective:** Make it feel like a complete platform.

Tasks:

* Role dashboards:

  * Patient: upcoming, past, docs, payments
  * Doctor: schedule, pending approvals, patient list
  * Admin: verification queue, platform metrics
* Email notifications (integration boundary):

  * appointment booked/approved/cancelled
  * verification approved/rejected
  * payment receipt

Definition of Done:

* Each role has a useful “home.”
* Emails send reliably in dev and can be configured for prod.

---

### Step 10 (Days 53–60): Security + Deployment Readiness + Exit Ramp

**Objective:** Production baseline and future NHS integration readiness.

Tasks:

* Security baseline:

  * enforce CSRF
  * secure cookies
  * rate limiting for auth endpoints
  * audit logs (who did what, when)
* Observability:

  * structured logging
  * error tracking integration (optional)
* Deployment:

  * switch to Postgres for prod
  * static/media strategy
  * gunicorn + reverse proxy guidance
* Exit ramp:

  * add JSON endpoints for key workflows
  * document API contracts
* Integration readiness:

  * create `integrations/nhs/` interface + placeholder service methods
  * ensure verification pipeline can accept external provider states

Definition of Done:

* `python manage.py check --deploy` passes with sane settings.
* Clear separation exists between product logic and integrations.
* Key workflows have both HTML and JSON pathways.

---

## NHS Integration “No Hassle” Plan (We prepare now)

We’ll make NHS-like integration easy by designing verification and identity as **pluggable providers**.

### Provider Interface (concept)

* `verify_doctor(provider, payload) -> VerificationResult`
* `link_identity(provider, oidc_sub, user) -> None`
* `sync_insurance(provider, patient) -> InsuranceProfile`

Your DoctorVerification state machine will support:

* manual admin verification (now)
* external identity verification (later)

Definition of Done (today):

* Verification is provider-driven, not hardcoded.

---

## How We Will Work “One by One”

You will say: **“Start Step X”**.
I will:

1. identify exact files to change
2. provide the code edits (or patch-style changes)
3. give a quick run/test checklist
4. confirm the Definition of Done for that step


