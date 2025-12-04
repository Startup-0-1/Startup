# 🏥 MedConsult  
A modern telemedicine platform built with **Django**, enabling patients and doctors to connect through secure appointments, document sharing, prescriptions, and payments.

MedConsult is designed as an end-to-end virtual healthcare experience — scalable, extensible, and compliant-ready. The MVP is fully functional and actively evolving toward a full telehealth ecosystem.

---

# 🚀 Features (Current MVP)

### ✅ **User Accounts & Roles**
- Custom user model with roles: **Patient**, **Doctor**, **Admin**
- Profile pages for both patients and doctors
- Login, registration, logout (HTML + API)

### ✅ **Appointment Booking System**
- Doctors define their availability
- Patients book 30-minute timeslots
- Doctors approve or reject requests
- Appointment grouping into time blocks
- Status tracking: requested, approved, rejected, completed, cancelled

### ✅ **Payments (Stripe Checkout)**
- One-time payment flow for appointments
- Stripe Checkout integration
- Payment status tracking

### ✅ **Documents & Prescriptions**
- Upload documents (lab reports, ID proofs, scans, etc.)
- Secure file storage
- Prescription upload & view system

### ✅ **Basic Role-Based Access Control**
- Patient-only, doctor-only, and admin-only protected views
- Decorators enforcing permissions

---

# 🔥 Features in Active Development

### 🔄 **Payment ↔ Appointment Linking**
- Appointments confirmed *only* after Stripe payment success  
- Add “Pending Payment” state

### 📬 **Email Notifications**
- Appointment booked/approved/rejected  
- Payment completed  
- New documents uploaded  
- New prescriptions added  

### 💬 **Real-Time Messaging**
- Patient ↔ Doctor chat  
- Live updates via Django Channels  

### 🎥 **Video Call Integration**
- Auto-generated consultation links (Zoom/Twilio/Jitsi)  
- “Join Call” button in appointment view  

---

# 🧭 Product Roadmap
A detailed roadmap is available in [`steps.md`](./medconsult/steps.md), including upcoming features such as:
- PDF prescription generator  
- Medical history timeline  
- Doctor ratings & reviews  
- 2FA security  
- Subscription plans  
- AI symptom checker  
- FHIR-style health data API  
- Docker deployment  
- Admin analytics dashboard  

---

# 📂 Project Structure

