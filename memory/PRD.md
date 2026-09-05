# PestControlPro — PRD

## Overview
Production-ready mobile-first Pest Control Service Management app built with Expo React Native + FastAPI + MongoDB. Role-based (Admin / Manager / Technician) with PIN authentication, photo-driven job execution, AMC contracts with auto-generated schedules, reminders, and WhatsApp feedback.

## Roles
- **Admin (Owner)**: full access including finances (revenue, charges, reports), user management, settings.
- **Manager**: full operations (customers, services, AMC, reminders) but no financials (charges/reports blocked at API level).
- **Technician**: only their assigned jobs; can start, upload before/during/after photos, enter medicine/quantity/notes, mark complete.

## Auth
- PIN-based (4 digits), bcrypt-hashed, JWT tokens.
- Seed admin: `admin` / `1234` (must change on first login).

## Data Model (MongoDB collections)
`users`, `customers`, `service_types`, `services`, `contracts` (AMC), `reminders`, `feedback`, `feedback_requests`, `settings`, `audit_logs`.

## Key Features
- Admin/Manager/Technician dashboards with role-specific KPIs.
- Full customer CRUD + service history.
- Service CRUD with status flow: pending → assigned → in_progress → completed / cancelled.
- Before/During/After photos via Emergent Managed Object Storage.
- AMC contracts with automatic schedule generation (daily/fortnightly/monthly/quarterly/custom).
- Reminders with computed states (upcoming/due/overdue/completed).
- Reports (admin only): revenue, by service type, technician performance.
- Settings: Google review URL, WhatsApp template. WhatsApp share via `wa.me` deep link.
- Audit log on service/user/AMC changes.

## Stack
- Backend: FastAPI, Motor (MongoDB), bcrypt, PyJWT, python-dateutil.
- Frontend: Expo Router, React Query, expo-image-picker, @react-native-community/datetimepicker.
- Storage: Emergent Managed Object Storage (photos).

## Localization
- Currency: INR (₹). Dates displayed as DD/MM/YYYY. Stored ISO. Timezone: IST (Asia/Kolkata).
