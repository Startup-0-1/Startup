

# # **MedConsult — A Modern Telehealth Platform **



MedConsult is a Django-based telehealth platform inspired by **Practo**, focused on the four features users actually love and desperately need:


* **Doctor Discovery**

* **Instant Appointment Booking**

* **Online Consultations (Chat/Video)**

* **Digital Prescriptions + Medical Records**



This README provides:



1. **What is already built**

2. **What needs to be built**

3. **A full Practo-style workflow**

4. **A complete technical roadmap (12-week plan)**

5. **Exact development steps (former Steps.md merged here)**

6. **How the codebase is structured + how to run everything**



This is the *master document*.


---

## 1. Current Progress (What’s Already Built)

| Feature Area                     | Status            | Notes                                                 |
|----------------------------------|-------------------|-------------------------------------------------------|
| User Auth (Doctor/Patient/Admin) | ✅ Done           | Working login, signup, roles                          |
| Doctor Profile Basics            | ⚠️ Partial        | Model exists, needs full verification workflow        |
| Patient Profile Basics           | ✅ Done           | Minimal fields implemented                            |
| Appointment System               | ⚠️ Partial        | Basic booking logic exists; needs availability engine |
| Prescription Module              | ⚠️ Partial        | Basic model; needs PDF + UI                           |
| File Uploads                     | ✅ Done           | Working for reports / documents                       |
| Dark/Light Theme                 | ✅ Done           | Cosmetic, works well                                  |
| Templates / Views                | ⚠️ Needs cleanup  | Several templates require restructuring               |
| Admin Panel                      | ⚠️ Basic          | Needs full doctor verification system                 |
| Search / Filters                 | ❌ Not implemented | High-priority                                         |
| Teleconsultation                 | ❌ Not implemented | Chat + optional video                                 |
| Payments                         | ❌ Not implemented | Required for real MVP                                 |

---



# # **2. What We’re Building (The Real MVP)**



A **lean, high-ROI version of Practo** that includes:



### **Core MVP Components**



* 🔍 Doctor Search (specialty, location, experience)

* 👤 Doctor Profile Pages

* 📅 Appointment Booking Engine with availability

* 💬 Online Consultation (Chat MVP)

* 📄 Digital Prescriptions (PDF)

* 🗂 Patient Medical Records

* 💳 Payment Gateway for online consults

* 🛠 Admin Doctor Verification



### **Not Included (Yet)**



* Pharmacy marketplace

* Insurance integrations

* Complex analytics

* Lab tests

* Hospital enterprise software



We go **fast**, not **bloated**.



---



# # **3. Full Practo-Style Workflow (Step-by-Step)**



This mirrors the real behavior of Practo but adapted to MedConsult.



---



## **3.1 Patient Workflow**



### **1. Signup / Login**



* Choose “Patient”

* Create profile → dashboard loads



### **2. Search for Doctors**



* Search by: specialty / city / name

* Filter results

* Open doctor profile



### **3. Book Appointment**



* Choose online or in-person

* Pick date + time slot

* (For online consults) → pay

* Appointment created + notifications sent



### **4. Consultation**



* Online chat or video

* Upload attachments

* Sync communication stored under session



### **5. Prescription & Records**



* Doctor issues prescription PDF

* Saved under “My Records” → downloadable



---



## **3.2 Doctor Workflow**



### **1. Registration**



* Upload verification documents

* Admin approval required



### **2. Profile Management**



* Fees, specialties, clinic, experience, availability



### **3. Appointment Management**



* Today’s schedule

* Accept/cancel

* Start consultation



### **4. Prescription Writing**



* Create prescription

* Save → auto-delivered to patient



---



## **3.3 Admin Workflow**



* Approve/Reject doctor applications

* Enable “Verified” badge

* View systemwide appointments

* Access payments dashboard

* Basic analytics



---



## **3.4 Backend System Workflow**



* Availability engine prevents double booking

* Notifications on every booking/update

* Payments gate teleconsultation confirmation

* Prescriptions PDF generator

* Medical record consolidation



---



# # **4. 12-Week Technical Roadmap**



This is your development plan, mapped realistically.



---



## **Phase 0 — Cleanup & Foundation (Week 1)**



* Reorganize project structure

* Standardize base templates

* Build custom user model (if not done)

* Separate settings (local/prod)

* Fix all broken templates

* Add `.env` support



---



## **Phase 1 — Core MVP: Search + Profiles + Appointments (Weeks 2–4)**



### **Week 2 — Doctor & Patient Profiles**



* Create full doctor/patient profile models

* Build profile UI pages

* Add admin doctor verification panel



### **Week 3 — Search & Discovery**



* Implement doctor search

* Specialty + location filters

* Search result UI



### **Week 4 — Appointment Booking Engine**



* Appointment model

* Availability engine

* Booking UI for patients

* Dashboard UI for doctors/patients



---



## **Phase 2 — Teleconsult + Prescriptions (Weeks 5–7)**



### **Week 5 — Chat Consultation**



* Consultation session model

* Messaging system

* Chat UI



### **Week 6 — Prescription Module**



* Prescription models

* PDF generation

* Doctor UI for prescriptions

* Patient records view



### **Week 7 — Patient Medical Records**



* Link prescriptions, appointments, messages

* Doctor can view patient history



---



## **Phase 3 — Payments + Admin Ops (Weeks 8–9)**



### **Week 8 — Payment Gateway**



* Payment model

* Payment success callback

* Prevent appointment confirmation until payment is processed



### **Week 9 — Admin Controls**



* Verification queue

* Payments dashboard

* Appointment global view



---



## **Phase 4 — Polish + Beta Release (Weeks 10–11)**



### **Week 10 — UX Polish**



* Consistent UI

* Error messaging

* Prevent broken form flows



### **Week 11 — Deploy Beta**



* Move to Postgres

* Deploy to Render/Railway

* Basic analytics

* Log errors + payment failures



---



## **Phase 5 — Real-World Iteration (Week 12+)**



* Fix doctor feedback issues

* Improve slot logic

* Add optional DRF API

* Begin planning mobile app



---



# # **5. Step-By-Step Build Instructions (Merged Steps.md)**



Follow these steps in order as you build the MVP.



---



## **Step 1 — Clean the Repository**



* Organize apps:



  ```

  core/

  accounts/

  profiles/

  appointments/

  prescriptions/

  consultations/

  ```

* Standardize templates and base layout

* Remove dead code



---



## **Step 2 — Implement User Roles**



* Add custom `User` model (if missing)

* Add `role = DOCTOR / PATIENT / ADMIN`

* Create profile models linked via OneToOne



---



## **Step 3 — Create Doctor & Patient Profiles**



* Doctor fields:



  * name

  * specialty

  * experience

  * clinic/hospital

  * fee

  * consultation types

  * availability

  * verification status

* Build create/edit/view forms



---



## **Step 4 — Build Search & Discovery**



* Search by:



  * doctor name

  * specialty

  * city

* Paginated results

* Doctor profile detail view



---



## **Step 5 — Appointment Booking Engine**



* `Appointment` model:



  * doctor

  * patient

  * date

  * slot

  * type

  * status

* Slot validation (no double-book)

* Patient → Book

* Doctor → Approve/Cancel

* Both → View schedule



---



## **Step 6 — Teleconsultation System (Chat MVP)**



* `ConsultationSession` + `Message` models

* Chat send/receive endpoints

* Auto-scrolling chatbox UI

* File uploads for reports



---



## **Step 7 — Prescription Module**



* Prescription model ± PrescriptionItem

* Doctor prescription form

* PDF generation

* Patient download page



---



## **Step 8 — Payment Integration**



* Use Stripe/Razorpay

* Add payment status

* Only confirm appointment on success



---



## **Step 9 — Admin Dashboard**



* Doctor verification queue

* Payment reports

* Appointment logs



---



## **Step 10 — Deployment**



* Convert DB → Postgres

* Push to Render/Railway

* Add environment variables

* Enable Static files + Media storage



---



# # **6. Project Structure (Recommended)**



```

medconsult/

├── accounts/

├── profiles/

├── appointments/

├── consultations/

├── prescriptions/

├── core/

├── templates/

├── static/

└── manage.py

```



---



# # **7. How to Run the Project**



```bash

# Create venv

python3 -m venv startup_venv

source startup_venv/bin/activate



# Install dependencies

pip install -r requirements.txt



# Run migrations

python manage.py makemigrations

python manage.py migrate



# Start server

python manage.py runserver

```



---



# # **8. Future Upgrades (After MVP)**



* Mobile App (Flutter/React Native)

* Video Consults (Agora/Twilio)

* Reviews/Ratings

* Insurance integrations

* DRF API for external integration



---



# # **9. License**



This project is proprietary as part of MedConsult startup.



---



