# CourseFinderBackend

Flask backend for user profiles, requirement progress tracking, and schedule/course suggestions.

## Setup

1. `python3 -m venv venv`
2. `source venv/bin/activate`
3. `pip install flask flask-sqlalchemy requests`
4. `python3 src/seed_courses.py` (cache Cornell course/offering data)
5. `python3 src/seed_requirements.py` (seed requirement rules)
6. `python3 src/app.py`

Server runs at `http://127.0.0.1:5000`.

## Frontend Integration Guide

### Core flow

1. Create/load a user (`POST /users/`, `GET /users/`)
2. Add completed courses (`POST /users/<user_id>/completed-courses/`)
3. Create schedule (`POST /users/<user_id>/schedules/`)
4. Add/remove planned offerings (`POST /schedules/<schedule_id>/offerings/`, `DELETE /schedules/<schedule_id>/offerings/<offering_id>/`)
5. Read requirement progress (`GET /users/<user_id>/progress/?schedule_id=<schedule_id>`)
6. Read recommendations (`GET /schedules/<schedule_id>/suggestions/`)

When adding offerings, send either:
- `offering_id` (internal DB id), or
- `class_nbr` (Cornell class number, scoped to schedule semester)

If a selected offering is a lecture (`LEC`), backend auto-adds the first valid discussion (`DIS`) section that does not conflict with the existing schedule.

### Important status mapping (frontend)

Backend returns progress statuses:
- `satisfied`
- `in_progress`
- `remaining`

If frontend enum is `COMPLETE | IN_PROGRESS | MISSING | RECOMMENDED`, map:
- `satisfied -> COMPLETE`
- `in_progress -> IN_PROGRESS`
- `remaining -> MISSING`
- `RECOMMENDED` comes from suggestions endpoint

### User payload fields

`POST /users/` accepts required:
- `name`
- `netid`
- `major`
- `year` (int)
- `college`
- `targetTerm` (or `target_term`)
- `targetCreditsLow` (or `target_credits_low`)
- `targetCreditsHigh` (or `target_credits_high`)

Optional:
- `school`
- `catalog_year`

`GET /users/` returns:
- Existing fields: `id`, `name`, `school`, `major`, `catalog_year`, `year`
- Added fields: `initial`, `netid`, `college`, `target_term`, `target_credits_low`, `target_credits_high`, `completed`

