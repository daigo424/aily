# aily — WhatsApp Booking Bot

A WhatsApp-based IT consulting reservation bot powered by Gemini and FastAPI.  
Customers book, reschedule, or cancel appointments through WhatsApp messages.  
Staff manage reservations through a Streamlit admin dashboard.

## Features

**Customer-facing (WhatsApp)**
- Receive and parse text, image, and audio messages
- Extract booking intent and date/time using Gemini structured output
- Follow-up questions when date or time is missing
- Conflict detection — rejects double-booking within 1-hour slots
- Cancellation flow — lists active reservations by number, lets customers confirm selection
- All replies in the same language as the customer's message

**Admin dashboard (Streamlit)**
- Reservation list with filters: pending / completed / voided / cancelled
- Per-reservation detail: timestamps for completion, voiding, and customer cancellation
- Status transitions: mark as completed or void (customer-cancelled reservations are locked)
- Customer conversation history viewer

## Reservation Statuses

| Status      | Set by              | Meaning                        |
|-------------|---------------------|--------------------------------|
| `pending`   | System              | Received, awaiting staff review |
| `completed` | Admin               | Consultation completed         |
| `voided`    | Admin               | Invalidated by staff           |
| `cancelled` | Customer (WhatsApp) | Cancelled by the customer      |

## Tech Stack

- **API**: FastAPI + Uvicorn
- **Admin**: Streamlit
- **LLM**: Google Gemini (`gemini-2.5-flash`)
- **DB**: PostgreSQL 17 + pgvector
- **Schema management**: Atlas
- **Package management**: uv
- **Linting / formatting**: Ruff
- **Type checking**: mypy

## Project Structure

```
src/
├── apps/
│   ├── api/          # WhatsApp webhook (FastAPI)
│   ├── admin/        # Admin dashboard (Streamlit)
└── packages/core/
    ├── config/       # Settings (pydantic-settings)
    ├── constants.py  # ReservationStatus, BookingRequestStatus, ConversationIntent
    ├── db/
    │   ├── models/   # SQLAlchemy ORM models
    │   └── repositories/
    ├── infrastructure/
    │   ├── chatapp/  # WhatsApp Cloud API client
    │   └── llm/      # Gemini client
    ├── schemas/      # Pydantic schemas
    └── usecases/     # Booking extraction logic
db/
└── app/schema/       # Atlas HCL schema definitions
```

## Prerequisites

- Docker / Docker Compose
- [uv](https://github.com/astral-sh/uv)
- [Atlas CLI](https://atlasgo.io)
- Meta WhatsApp Cloud API credentials
- Gemini API key
- Public URL (ngrok or Cloudflare Tunnel)

## Setup

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

| Variable                    | Description                                        |
|-----------------------------|----------------------------------------------------|
| `APP_BASE_URL`              | Your public URL (e.g. ngrok URL)                   |
| `LOCAL_PUBLISH_DOMAIN`      | Domain only, without `https://`                    |
| `VERIFY_TOKEN`              | Arbitrary token for WhatsApp webhook verification  |
| `WHATSAPP_TOKEN`            | WhatsApp Cloud API token                           |
| `WHATSAPP_PHONE_NUMBER_ID`  | WhatsApp phone number ID                           |
| `WHATSAPP_GRAPH_API_VERSION`| e.g. `v24.0`                                       |
| `GEMINI_API_KEY`            | Google Gemini API key                              |
| `GEMINI_MODEL`              | e.g. `gemini-2.5-flash`                            |
| `TIMEZONE`                  | e.g. `Asia/Tokyo`                                  |

### 2. Start services

```bash
make up
```

This starts:
- `api` — FastAPI app on port 8000
- `admin` — Streamlit dashboard on port 8501
- `db` — PostgreSQL + pgvector on port 5432

### 3. Apply database schema

```bash
make atlas-apply
```

### 4. Expose the local server

```bash
make publish
```

Uses ngrok with the domain configured in `LOCAL_PUBLISH_DOMAIN`.

### 5. Configure the WhatsApp webhook

In the Meta Developer Console:

- **Callback URL**: `https://<your-domain>/webhook`
- **Verify Token**: value of `VERIFY_TOKEN` in `.env`
- **Subscribe fields**: `messages`

## Development

```bash
# Run all checks
make all-check

# Individual checks
make format        # Ruff format
make lint          # Ruff lint
make typecheck     # mypy
make test          # pytest

# Update requirements files from pyproject.toml
make update-req
```

> **Note:** `requirements.txt` and `requirements-dev.txt` are generated from `pyproject.toml` via `uv export`.  
> A GitHub Actions workflow blocks merges when they are out of sync.

## Database Tables

| Table             | Description                                                     |
|-------------------|-----------------------------------------------------------------|
| `customers`       | Phone number and name                                           |
| `conversations`   | Per-customer chat session with intent and cancel flow state     |
| `messages`        | All inbound and outbound messages                               |
| `booking_requests` | Booking info being collected (collecting → ready → confirmed)  |
| `reservations`    | Confirmed reservations with status lifecycle                    |

## CI

`.github/workflows/check-requirements.yml` runs on PRs that touch `pyproject.toml` or `uv.lock` and fails if `requirements.txt` / `requirements-dev.txt` are stale.
