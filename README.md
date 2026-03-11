# Academix

A full-stack university academic management system designed to centralize the administration of careers, subjects, schedules, grades, messaging, and study materials in a single platform.

---

## Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [System Modules](#system-modules)
- [User Roles](#user-roles)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Available Commands](#available-commands)
- [Environment Variables](#environment-variables)
- [API](#api)

---

## Overview

Academix is a web-based academic platform that provides comprehensive management of university institution processes. It offers role-differentiated functionality for students, teachers, academic management staff, and system administrators.

Key capabilities:

- Management of careers, subjects, academic periods, and classrooms
- Student enrollment in careers and individual classes
- Grade recording and consultation per evaluation
- Study material upload and download
- Internal messaging between users
- Notification system
- Academic statistics and reports
- Administrative panel with full system control

---

## Tech Stack

### Backend
| Technology | Version | Role |
|---|---|---|
| Python / Django | 5.x | Main framework |
| Django REST Framework | 3.14+ | REST API |
| SimpleJWT | 5.3+ | JWT authentication |
| PostgreSQL | 16 | Database (production) |
| SQLite | — | Database (development) |
| Gunicorn | 21+ | WSGI server (production) |

### Frontend
| Technology | Version | Role |
|---|---|---|
| Astro | 5.x | UI framework |
| TailwindCSS | 4.x | Styling |
| Zustand | 5.x | Global state management |
| TypeScript | — | Static typing |
| Vitest | 1.x | Testing |

### Infrastructure
| Technology | Role |
|---|---|
| Docker / Docker Compose | Containerization |
| Nginx | Static file server and reverse proxy (production) |

---

## Architecture

```
┌─────────────────────────────────────────────┐
│                    Client                   │
│           Astro + TailwindCSS + Zustand     │
│               (Port 4321 / 80)              │
└───────────────────────┬─────────────────────┘
                        │ HTTP / REST
┌───────────────────────▼─────────────────────┐
│              Django REST Framework          │
│           JWT Auth · CORS · Gunicorn        │
│                  (Port 8000)                │
└───────────────────────┬─────────────────────┘
                        │
┌───────────────────────▼─────────────────────┐
│          PostgreSQL 16  (production)        │
│          SQLite         (development)       │
└─────────────────────────────────────────────┘
```

In production, Nginx serves the static frontend and acts as a reverse proxy to the backend on port 8000. All three services run on a private Docker network (`academix-network`).

---

## System Modules

### `users` — User management
- Extended `AbstractUser` model with additional fields: role, phone, address, date of birth, and profile image.
- Four supported roles: student, teacher, management, and administration.

### `academic` — Academic structure
- **Career**: university degree programs with code, duration, and active status.
- **Subject**: courses linked to a career, with credits and weekly hours.
- **AcademicPeriod**: academic terms with start and end dates.
- **Classroom**: rooms with capacity and type (lecture hall, laboratory, seminar room).
- **Class**: instance of a subject in a period, assigned to a teacher and classroom.
- **ClassSchedule**: weekly timetable per class.

### `enrollment` — Enrollments
- **CareerEnrollment**: student enrollment in a career for a given period (statuses: pending, active, completed, dropped).
- **ClassEnrollment**: enrollment in individual classes (statuses: enrolled, waitlisted, dropped).

### `grades` — Grades
- **Evaluation**: assessments per class (exam, assignment, quiz, project, participation) with maximum score and due date.
- **Grade**: individual student grade with feedback and an audit trail of who recorded it.

### `material` — Study materials
- File attachments and external links organized per class.
- Supported types: document, video, link, and other.

### `messaging` — Internal messaging
- Direct messages between any pair of users with threaded reply support.
- Independent soft-delete control for sender and recipient.

### `notifications` — Notifications
- Per-user system notifications classified as info, success, warning, and error.
- Individual read/unread tracking.

---

## User Roles

| Role | Code | Main access |
|---|---|---|
| Student | My classes, enrollments, grades, materials, messages |
| Teacher | My subjects, students, grades, materials, schedules |
| Academic management | Careers, periods, classrooms, enrollments, statistics, reports |
| Administration | Full system control, users, configuration |

---

## Prerequisites

- [Docker](https://www.docker.com/) and Docker Compose v2
- `make` (optional but recommended for Makefile commands)

---

## Getting Started

### Development

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd academix
   ```

2. Create the development environment file:
   ```bash
   cp .env.dev.example .env.dev
   # Edit .env.dev with the appropriate values
   ```

3. Start the services:
   ```bash
   make dev-up
   ```

4. Apply database migrations:
   ```bash
   make migrate
   ```

5. Create a superuser:
   ```bash
   make createsuperuser
   ```

Services will be available at:
- **Frontend**: http://localhost:4321
- **Backend / API**: http://localhost:8000/api/
- **Django Admin**: http://localhost:8000/admin/

### Production

1. Create the production environment file:
   ```bash
   cp .env.prod.example .env.prod
   # Configure database, secret key, allowed hosts, etc.
   ```

2. Build and start the services:
   ```bash
   make prod-up
   ```

3. Apply migrations and create a superuser:
   ```bash
   make prod-migrate
   make prod-createsuperuser
   ```

The application will be available at http://localhost (port 80).

---

## Available Commands

Run `make help` to see all available commands. The most commonly used ones:

| Command | Description |
|---|---|
| `make dev-up` | Start development environment |
| `make dev-down` | Stop development environment |
| `make dev-logs` | Tail logs in real time (dev) |
| `make dev-rebuild` | Rebuild images without cache (dev) |
| `make migrate` | Run Django migrations (dev) |
| `make createsuperuser` | Create Django superuser (dev) |
| `make backend-shell` | Open a shell in the backend container |
| `make frontend-shell` | Open a shell in the frontend container |
| `make prod-up` | Start production environment |
| `make prod-migrate` | Run Django migrations (prod) |
| `make prod-createsuperuser` | Create Django superuser (prod) |
| `make clean` | Remove all containers and volumes |

---

## Environment Variables

### `.env.dev`

```env
SECRET_KEY=your-dev-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:4321
```

### `.env.prod`

```env
SECRET_KEY=your-secure-secret-key
DEBUG=False
ALLOWED_HOSTS=your-domain.com
CORS_ALLOWED_ORIGINS=https://your-domain.com

POSTGRES_DB=academix
POSTGRES_USER=academix_user
POSTGRES_PASSWORD=secure-password
POSTGRES_HOST=db
POSTGRES_PORT=5432
```

---

## API

The REST API is available under the `/api/` prefix. Authentication is handled via JWT:

- `POST /api/token/` — Obtain access and refresh tokens
- `POST /api/token/refresh/` — Renew the access token

Include the token in requests:
```
Authorization: Bearer <access_token>
```

The Django admin panel is available at `/admin/` for staff users.
