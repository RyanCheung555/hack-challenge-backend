from app import create_app
from db import db, User, Schedule, ScheduleOffering, CourseOffering
from services.requirements import build_course_tags, evaluate_requirement_progress
from services.recommendations import build_suggestions_for_schedule

app = create_app()

with app.app_context():
    session = db.session

    # ---------------------------
    # 1. TAG TEST
    # ---------------------------
    tags = build_course_tags(session)

    print("TAGS SAMPLE:")
    for k, v in list(tags.items())[:10]:
        print(k, v)

    # ---------------------------
    # 2. CREATE USER
    # ---------------------------
    existing_user = User.query.filter_by(
        name="test_user",
        major="CS",
        year=1
    ).first()

    if existing_user:
        user = existing_user
        print("\nUsing existing user:", user.id)
    else:
        user = User(
            name="test_user",
            major="CS",
            school="engineering",
            catalog_year="any",
            year=1
        )
        db.session.add(user)
        db.session.commit()
        print("\nCreated user:", user.id)

    # ---------------------------
    # 3. REQUIREMENTS TEST
    # ---------------------------
    completed = ["CS1110", "MATH1910"]
    planned = ["CS2110"]

    result = evaluate_requirement_progress(
        user,
        completed,
        planned,
        {},     # credits (fine for now)
        tags
    )

    print("\nREQUIREMENT RESULT:")
    for r in result["rules"]:
        print(r["title"], "→", r["status"])

    # ---------------------------
    # 4. CREATE SCHEDULE
    # ---------------------------
    existing_schedule = Schedule.query.filter_by(
        user_id=user.id,
        semester="FA26",
        name="My Schedule"
    ).first()

    if existing_schedule:
        schedule = existing_schedule
        print("\nUsing existing schedule:", schedule.id)
    else:
        schedule = Schedule(
            user_id=user.id,
            semester="FA26",
            name="My Schedule"
        )
        db.session.add(schedule)
        db.session.commit()
        print("\nCreated schedule:", schedule.id)

    # ---------------------------
    # 5. ADD ONE OFFERING
    # ---------------------------
    offering = CourseOffering.query.first()

    existing_so = ScheduleOffering.query.filter_by(
        schedule_id=schedule.id,
        offering_id=offering.id
    ).first()

    if existing_so:
        print("Offering already in schedule")
    else:
        db.session.add(ScheduleOffering(
            schedule_id=schedule.id,
            offering_id=offering.id
        ))
        db.session.commit()
        print("Added offering:", offering.course.course_id, offering.section)

    # ---------------------------
    # 6. SUGGESTIONS TEST
    # ---------------------------
    response, status = build_suggestions_for_schedule(schedule.id)

    print("\nSTATUS:", status)

    suggestions = response.get("suggestions", [])

    print("\nSUGGESTIONS:")
    for s in suggestions[:10]:
        print(
            s["course_id"],
            "|",
            s["title"],
            "|",
            s["days"],
            s["start_time"],
            "→",
            s["reason_codes"]
        )