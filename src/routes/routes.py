from flask import Blueprint, jsonify, request

try:
    from src.db import (
        CachedCourse,
        CompletedCourse,
        CourseOffering,
        MajorRequirement,
        RequirementCourse,
        RequirementRule,
        RequirementSet,
        DistributionSet,
        Schedule,
        ScheduleOffering,
        User,
        db,
    )
    from src.services.recommendations import build_suggestions_for_schedule
    from src.services.requirements import evaluate_requirement_progress
    from src.services.scheduler import has_conflict_with_schedule
except ModuleNotFoundError:
    from db import (
        CachedCourse,
        CompletedCourse,
        CourseOffering,
        MajorRequirement,
        RequirementCourse,
        RequirementRule,
        RequirementSet,
        DistributionSet,
        Schedule,
        ScheduleOffering,
        User,
        db,
    )
    from services.recommendations import build_suggestions_for_schedule
    from services.requirements import evaluate_requirement_progress
    from services.scheduler import has_conflict_with_schedule

main = Blueprint("main", __name__)


def _derive_initial(name: str) -> str:
    parts = [part for part in (name or "").strip().split() if part]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0][0].upper()
    return f"{parts[0][0]}{parts[-1][0]}".upper()


def _serialize_user(user: User) -> dict:
    completed_codes = sorted(row.course.course_id.upper() for row in user.completed_courses)
    distributions = (user.distributions[0].completed_distributions if user.distributions else [])
    return {
        "id": user.id,
        "name": user.name,
        "initial": _derive_initial(user.name),
        "netid": user.netid,
        "school": user.school,
        "college": user.college,
        "major": user.major,
        "completed_distributions": distributions,
        "catalog_year": user.catalog_year,
        "year": user.year,
        "target_term": user.target_term,
        "target_credits_low": user.target_credits_low,
        "target_credits_high": user.target_credits_high,
        "completed": completed_codes,
    }


@main.get("/")
def health_check() -> str:
    return "CourseFinderBackend is running."


@main.post("/users/")
def create_user():
    payload = request.get_json(silent=True) or {}

    required_fields = ("name", "major", "year", "college", "netid")
    missing = [field for field in required_fields if payload.get(field) in (None, "")]
    target_term = payload.get("targetTerm", payload.get("target_term"))
    target_credits_low = payload.get("targetCreditsLow", payload.get("target_credits_low"))
    target_credits_high = payload.get("targetCreditsHigh", payload.get("target_credits_high"))

    if target_term in (None, ""):
        missing.append("targetTerm")
    if target_credits_low in (None, ""):
        missing.append("targetCreditsLow")
    if target_credits_high in (None, ""):
        missing.append("targetCreditsHigh")

    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    try:
        target_credits_low = int(target_credits_low)
        target_credits_high = int(target_credits_high)
        if target_credits_low > target_credits_high:
            return jsonify({"error": "target_credits_low cannot exceed target_credits_high"}), 400

        existing_user = User.query.filter_by(netid=str(payload.get("netid", "")).strip()).first()
        if existing_user:
            return jsonify(
                {
                    "error": "User with this netid already exists",
                    "user_id": existing_user.id,
                    "netid": existing_user.netid,
                }
            ), 409

        user = User(
            name=str(payload["name"]).strip(),
            school=str(payload.get("school", "unknown")).strip(),
            college=str(payload.get("college", "")).strip(),
            netid=str(payload.get("netid", "")).strip(),
            major=str(payload["major"]).strip(),
            catalog_year=str(payload.get("catalog_year", "any")).strip(),
            year=int(payload["year"]),
            target_term=str(target_term).strip(),
            target_credits_low=target_credits_low,
            target_credits_high=target_credits_high,
        )
        if not user.name or not user.major or not user.college or not user.netid or not user.target_term:
            return jsonify({"error": "Required string fields cannot be empty"}), 400
        db.session.add(user)
        db.session.commit()
        return jsonify(_serialize_user(user)), 201
    except Exception as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


@main.get("/users/")
def list_users():
    users = User.query.all()
    return jsonify([_serialize_user(user) for user in users])


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

DISTRIBUTION_FIELDS = ["ALC", "BIO", "ETM", "GLC", "HST", "PHS", "SCD", "SSC", "SDS", "SMR"]
@main.post("/users/<int:user_id>/distributions/")
def add_distributions(user_id):
    data = request.get_json()

    for field in DISTRIBUTION_FIELDS:
        value = data.get(field)
        if value is None:
            value = 0

        if value not in (0, 1, True, False):
            return jsonify({"error": f"{field} is of invalid format"}), 400
    ds = DistributionSet.query.filter_by(user_id=user_id).first()
    if ds is None:
        ds = DistributionSet(user_id=user_id)
    for field in DISTRIBUTION_FIELDS:
        setattr(ds, field, bool(data.get(field, 0)))

    db.session.add(ds)
    db.session.commit()

    return jsonify({"completed distributions": ds.completed_distributions}), 200    

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
    class_nbr = payload.get("class_nbr")
    if offering_id is None and class_nbr is None:
        return jsonify({"error": "One of offering_id or class_nbr is required"}), 400

    schedule = Schedule.query.get(schedule_id)
    if not schedule:
        return jsonify({"error": "Schedule not found"}), 404

    offering = None
    if offering_id is not None:
        offering = db.session.get(CourseOffering, int(offering_id))
    elif class_nbr is not None:
        offering = CourseOffering.query.filter_by(
            semester=schedule.semester,
            class_nbr=int(class_nbr),
        ).first()

    if not offering:
        return jsonify({"error": "Offering not found"}), 404

    planned_offerings = [row.offering for row in schedule.planned_offerings]
    if has_conflict_with_schedule(offering, planned_offerings):
        return jsonify({"error": "Offering conflicts with existing schedule"}), 409

    existing = ScheduleOffering.query.filter_by(
        schedule_id=schedule_id, offering_id=offering.id
    ).first()
    if existing:
        return jsonify({"message": "Offering already in schedule"}), 200

    added_offerings = []
    row = ScheduleOffering(schedule_id=schedule_id, offering_id=offering.id)
    db.session.add(row)
    added_offerings.append(offering.id)

    # Auto-attach one valid discussion section for selected lectures.
    if (offering.component or "").upper() == "LEC":
        discussions = (
            db.session.query(type(offering))
            .filter_by(
                course_id=offering.course_id,
                semester=offering.semester,
                component="DIS",
            )
            .all()
        )

        existing_offering_ids = {planned.id for planned in planned_offerings}
        valid_discussions = []
        for dis in discussions:
            if dis.id in existing_offering_ids:
                continue
            if has_conflict_with_schedule(dis, planned_offerings + [offering]):
                continue
            valid_discussions.append(dis)

        if not valid_discussions:
            db.session.rollback()
            return jsonify(
                {
                    "error": "No valid discussion section available for this lecture",
                    "offering_id": offering.id,
                }
            ), 409

        valid_discussions.sort(key=lambda dis: (dis.section or "", dis.id))
        chosen_discussion = valid_discussions[0]
        db.session.add(
            ScheduleOffering(schedule_id=schedule_id, offering_id=chosen_discussion.id)
        )
        added_offerings.append(chosen_discussion.id)

    db.session.commit()
    return jsonify(
        {
            "schedule_id": schedule_id,
            "added_offering_ids": added_offerings,
        }
    ), 201


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
