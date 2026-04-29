from flask import Blueprint, jsonify, request

try:
    from src.db import (
        CachedCourse,
        CompletedCourse,
        MajorRequirement,
        RequirementCourse,
        RequirementRule,
        RequirementSet,
        Schedule,
        ScheduleOffering,
        User,
        db,
    )
    from src.services.recommendations import build_suggestions_for_schedule
    from src.services.requirements import evaluate_requirement_progress
except ModuleNotFoundError:
    from db import (
        CachedCourse,
        CompletedCourse,
        MajorRequirement,
        RequirementCourse,
        RequirementRule,
        RequirementSet,
        Schedule,
        ScheduleOffering,
        User,
        db,
    )
    from services.recommendations import build_suggestions_for_schedule
    from services.requirements import evaluate_requirement_progress

main = Blueprint("main", __name__)


@main.get("/")
def health_check() -> str:
    return "CourseFinderBackend is running."


@main.post("/users/")
def create_user():
    payload = request.get_json(silent=True) or {}

    required_fields = ("name", "major", "year")
    missing = [field for field in required_fields if payload.get(field) in (None, "")]

    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    try:
        user = User(
            name=str(payload["name"]).strip(),
            school=str(payload.get("school", "unknown")).strip(),
            major=str(payload["major"]).strip(),
            catalog_year=str(payload.get("catalog_year", "any")).strip(),
            year=int(payload["year"]),
        )
        db.session.add(user)
        db.session.commit()
        return jsonify(
            {
                "id": user.id,
                "name": user.name,
                "school": user.school,
                "major": user.major,
                "catalog_year": user.catalog_year,
                "year": user.year,
            }
        ), 201
    except Exception as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


@main.get("/users/")
def list_users():
    users = User.query.all()
    return jsonify(
        [
            {
                "id": user.id,
                "name": user.name,
                "school": user.school,
                "major": user.major,
                "catalog_year": user.catalog_year,
                "year": user.year,
            }
            for user in users
        ]
    )


@main.post("/users/<int:user_id>/completed-courses/")
def add_completed_course(user_id):
    payload = request.get_json(silent=True) or {}
    course_code = str(payload.get("course_id", "")).strip().upper()
    if not course_code:
        return jsonify({"error": "Missing required field: course_id"}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    course = CachedCourse.query.filter_by(course_id=course_code).first()
    if not course:
        return jsonify({"error": "Cached course not found"}), 404

    exists = CompletedCourse.query.filter_by(user_id=user_id, course_id=course.id).first()
    if exists:
        return jsonify({"message": "Course already marked completed"}), 200

    row = CompletedCourse(user_id=user_id, course_id=course.id)
    db.session.add(row)
    db.session.commit()
    return jsonify({"user_id": user_id, "course_id": course.course_id}), 201


@main.post("/users/<int:user_id>/schedules/")
def create_schedule(user_id):
    payload = request.get_json(silent=True) or {}
    semester = str(payload.get("semester", "")).strip().upper()
    if not semester:
        return jsonify({"error": "Missing required field: semester"}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    schedule = Schedule(
        user_id=user_id,
        name=str(payload.get("name", "My Schedule")).strip() or "My Schedule",
        semester=semester,
        status=str(payload.get("status", "active")).strip() or "active",
    )
    db.session.add(schedule)
    db.session.commit()
    return jsonify(
        {
            "id": schedule.id,
            "user_id": schedule.user_id,
            "name": schedule.name,
            "semester": schedule.semester,
            "status": schedule.status,
        }
    ), 201


@main.post("/schedules/<int:schedule_id>/offerings/")
def add_schedule_offering(schedule_id):
    payload = request.get_json(silent=True) or {}
    offering_id = payload.get("offering_id")
    if offering_id is None:
        return jsonify({"error": "Missing required field: offering_id"}), 400

    schedule = Schedule.query.get(schedule_id)
    if not schedule:
        return jsonify({"error": "Schedule not found"}), 404

    existing = ScheduleOffering.query.filter_by(
        schedule_id=schedule_id, offering_id=int(offering_id)
    ).first()
    if existing:
        return jsonify({"message": "Offering already in schedule"}), 200

    row = ScheduleOffering(schedule_id=schedule_id, offering_id=int(offering_id))
    db.session.add(row)
    db.session.commit()
    return jsonify({"id": row.id, "schedule_id": row.schedule_id, "offering_id": row.offering_id}), 201


@main.delete("/schedules/<int:schedule_id>/offerings/<int:offering_id>/")
def remove_schedule_offering(schedule_id, offering_id):
    row = ScheduleOffering.query.filter_by(schedule_id=schedule_id, offering_id=offering_id).first()
    if not row:
        return jsonify({"error": "Offering not found in schedule"}), 404
    db.session.delete(row)
    db.session.commit()
    return jsonify({"removed": True})


@main.get("/users/<int:user_id>/progress/")
def get_user_progress(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    schedule_id = request.args.get("schedule_id", type=int)
    planned_codes = set()
    if schedule_id:
        schedule = Schedule.query.get(schedule_id)
        if not schedule or schedule.user_id != user.id:
            return jsonify({"error": "Schedule not found for user"}), 404
        planned_codes = {row.offering.course.course_id.upper() for row in schedule.planned_offerings}

    completed_rows = CompletedCourse.query.filter_by(user_id=user_id).all()
    completed_codes = {row.course.course_id.upper() for row in completed_rows}

    courses = CachedCourse.query.all()
    credit_by_code = {(course.course_id or "").upper(): (course.credits or 0) for course in courses}
    tag_by_code = {
        (course.course_id or "").upper(): {tag.tag.upper() for tag in course.tags}
        for course in courses
    }
    progress = evaluate_requirement_progress(
        user,
        completed_codes,
        planned_codes,
        credit_by_code,
        tag_by_code,
    )
    return jsonify(progress)


@main.get("/schedules/<int:schedule_id>/suggestions/")
def get_schedule_suggestions(schedule_id):
    limit = request.args.get("limit", default=25, type=int)
    payload, code = build_suggestions_for_schedule(schedule_id, limit=limit)
    return jsonify(payload), code


@main.post("/major-requirements/")
def create_major_requirement():
    payload = request.get_json(silent=True) or {}

    required_fields = ("major", "requirement_group", "requirement_type", "course_id")
    missing = [field for field in required_fields if payload.get(field) in (None, "")]

    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    try:
        req = MajorRequirement(
            major=str(payload["major"]).strip(),
            requirement_group=str(payload["requirement_group"]).strip(),
            requirement_type=str(payload["requirement_type"]).strip(),
            course_id=str(payload["course_id"]).strip(),
            group_id=(str(payload["group_id"]).strip() if payload.get("group_id") else None),
        )
        db.session.add(req)
        db.session.commit()
        return jsonify(
            {
                "id": req.id,
                "major": req.major,
                "requirement_group": req.requirement_group,
                "requirement_type": req.requirement_type,
                "course_id": req.course_id,
                "group_id": req.group_id,
            }
        ), 201
    except Exception as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


@main.get("/major-requirements/")
def list_major_requirements():
    major = request.args.get("major")

    query = MajorRequirement.query
    if major:
        query = query.filter(MajorRequirement.major == major)

    rows = query.all()

    return jsonify(
        [
            {
                "id": row.id,
                "major": row.major,
                "requirement_group": row.requirement_group,
                "requirement_type": row.requirement_type,
                "course_id": row.course_id,
                "group_id": row.group_id,
            }
            for row in rows
        ]
    )


@main.post("/requirements/sets/")
def create_requirement_set():
    payload = request.get_json(silent=True) or {}
    required_fields = ("scope", "scope_key")
    missing = [field for field in required_fields if payload.get(field) in (None, "")]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    row = RequirementSet(
        scope=str(payload["scope"]).strip().lower(),
        scope_key=str(payload["scope_key"]).strip(),
        catalog_year=str(payload.get("catalog_year", "any")).strip() or "any",
    )
    db.session.add(row)
    db.session.commit()
    return jsonify({"id": row.id, "scope": row.scope, "scope_key": row.scope_key, "catalog_year": row.catalog_year}), 201


@main.post("/requirements/rules/")
def create_requirement_rule():
    payload = request.get_json(silent=True) or {}
    required_fields = ("requirement_set_id", "group_id", "rule_type", "title")
    missing = [field for field in required_fields if payload.get(field) in (None, "")]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    rule = RequirementRule(
        requirement_set_id=int(payload["requirement_set_id"]),
        group_id=str(payload["group_id"]).strip(),
        rule_type=str(payload["rule_type"]).strip(),
        n_required=payload.get("n_required"),
        credits_min=payload.get("credits_min"),
        title=str(payload["title"]).strip(),
    )
    db.session.add(rule)
    db.session.commit()
    return jsonify({"id": rule.id}), 201


@main.post("/requirements/rules/<int:rule_id>/courses/")
def add_requirement_course(rule_id):
    payload = request.get_json(silent=True) or {}
    if not payload.get("course_id") and not payload.get("course_tag"):
        return jsonify({"error": "One of course_id or course_tag is required"}), 400

    row = RequirementCourse(
        requirement_rule_id=rule_id,
        course_id=(str(payload["course_id"]).strip().upper() if payload.get("course_id") else None),
        course_tag=(str(payload["course_tag"]).strip().upper() if payload.get("course_tag") else None),
    )
    db.session.add(row)
    db.session.commit()
    return jsonify({"id": row.id}), 201
