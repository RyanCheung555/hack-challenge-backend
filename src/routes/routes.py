from flask import Blueprint, jsonify, request
from typing import Optional

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
    from src.db import remove_schedule_offering_cascade
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
    from db import remove_schedule_offering_cascade
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


def _serialize_course(course: CachedCourse) -> dict:
    tags = sorted(tag.tag for tag in course.tags)
    return {
        "id": course.id,
        "courseId": course.course_id,
        "name": course.title,
        "department": course.department,
        "courseNumber": course.number,
        "credits": course.credits,
        "description": course.description,
        "prerequisites": course.prerequisites,
        "corequisites": course.corequisites,
        "distributions": course.distributions,
        "tags": tags,
    }


def _serialize_offering(offering: CourseOffering) -> dict:
    return {
        "id": offering.id,
        "semester": offering.semester,
        "classNbr": offering.class_nbr,
        "section": offering.section,
        "component": offering.component,
        "instructor": offering.instructor,
        "days": offering.days,
        "startTime": offering.start_time,
        "endTime": offering.end_time,
        "time": (
            f"{offering.start_time}-{offering.end_time}"
            if offering.start_time and offering.end_time
            else None
        ),
        "location": offering.location,
    }


def _serialize_course_with_offerings(course: CachedCourse, semester: Optional[str] = None) -> dict:
    payload = _serialize_course(course)
    offerings = course.offerings
    if semester:
        normalized = semester.strip().upper()
        offerings = [offering for offering in offerings if (offering.semester or "").upper() == normalized]

    payload["offerings"] = [_serialize_offering(offering) for offering in offerings]
    payload["open"] = bool(offerings)
    return payload


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


@main.get("/courses")
def list_courses():
    query = CachedCourse.query

    subject = request.args.get("subject", type=str)
    if subject:
        query = query.filter(CachedCourse.department.ilike(subject.strip()))

    credits = request.args.get("credits", type=int)
    if credits is not None:
        query = query.filter(CachedCourse.credits == credits)

    search_term = request.args.get("q", type=str) or request.args.get("search", type=str)
    if search_term:
        term = f"%{search_term.strip()}%"
        query = query.filter(
            db.or_(
                CachedCourse.course_id.ilike(term),
                CachedCourse.title.ilike(term),
                CachedCourse.description.ilike(term),
            )
        )

    courses = query.order_by(CachedCourse.course_id.asc()).all()

    semester = request.args.get("semester", type=str)
    if semester:
        normalized = semester.strip().upper()
        courses = [
            course for course in courses
            if any((offering.semester or "").upper() == normalized for offering in course.offerings)
        ]

    return jsonify([_serialize_course_with_offerings(course, semester=semester) for course in courses])


@main.get("/courses/<string:course_id>")
def get_course(course_id: str):
    normalized = course_id.strip().upper()
    course = CachedCourse.query.filter_by(course_id=normalized).first()
    if not course:
        return jsonify({"error": "Course not found"}), 404
    semester = request.args.get("semester", type=str)
    return jsonify(_serialize_course_with_offerings(course, semester=semester))


@main.get("/courses/semesters")
def list_course_semesters():
    rows = (
        db.session.query(CourseOffering.semester)
        .distinct()
        .order_by(CourseOffering.semester.asc())
        .all()
    )
    semesters = [row[0] for row in rows if row[0]]
    return jsonify({"semesters": semesters})


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


def _serialize_schedule_summary(schedule: Schedule) -> dict:
    return {
        "id": schedule.id,
        "user_id": schedule.user_id,
        "name": schedule.name,
        "semester": schedule.semester,
        "status": schedule.status,
        "planned_count": len(schedule.planned_offerings),
    }


@main.get("/users/<int:user_id>/schedules/")
def list_user_schedules(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    query = Schedule.query.filter_by(user_id=user_id).order_by(
        Schedule.semester.desc(), Schedule.id.desc()
    )
    semester = request.args.get("semester", type=str)
    if semester:
        query = query.filter(
            Schedule.semester == str(semester).strip().upper()
        )
    schedules = query.all()
    return jsonify(
        {
            "schedules": [_serialize_schedule_summary(s) for s in schedules],
        }
    )


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
    if (offering.component or "") == "LEC":
        children = (
            CourseOffering.query
            .filter(
                CourseOffering.course_id == offering.course_id,
                CourseOffering.semester == offering.semester,
                CourseOffering.component.isnot(None),
                CourseOffering.component != "LEC",
            )
            .all()
        )
        # Bucket candidates by component type: {"DIS": [...], "PRJ": [...], ...}
        by_component: dict[str, list[CourseOffering]] = {}
        for c in children:
            by_component.setdefault((c.component or ""), []).append(c)

        existing_offering_ids = {planned.id for planned in planned_offerings}
        chosen_dependents = []
        
        for comp, options in by_component.items(): # by comp type
            # If user already has one of this component, skip
            if any(opt.id in existing_offering_ids for opt in options):
                continue
            valid = [
                opt for opt in options
                if not has_conflict_with_schedule(opt, planned_offerings+chosen_dependents)
            ]
            if not valid:
                db.session.rollback()
                return jsonify({
                    "error": f"No valid {comp} section available for this lecture",
                    "offering_id": offering.id,
                }), 409
            valid.sort(key=lambda x: (x.section or "", x.id))
            chosen = valid[0] # first valid section
            db.session.add(
                ScheduleOffering(schedule_id=schedule_id, offering_id=chosen.id)
            )
            added_offerings.append(chosen.id)
            chosen_dependents.append(chosen) # add chosen if offering is in fact valid

    db.session.commit()
    return jsonify(
        {
            "schedule_id": schedule_id,
            "added_offering_ids": added_offerings,
            "planned_offerings": [
                {
                    "offering_id": so.offering_id,
                    "course_id": so.offering.course.course_id,
                    "component": so.offering.component,
                    "section": so.offering.section,
                }
                for so in schedule.planned_offerings
            ]    
        }
    ), 201


def _serialize_schedule(schedule: Schedule) -> dict:
    rows = []
    for so in schedule.planned_offerings:
        off = so.offering
        row = _serialize_offering(off)
        row["offering_id"] = off.id
        row["course_code"] = off.course.course_id
        rows.append(row)
    return {
        "id": schedule.id,
        "user_id": schedule.user_id,
        "name": schedule.name,
        "semester": schedule.semester,
        "status": schedule.status,
        "planned_offerings": rows,
    }


@main.get("/schedules/<int:schedule_id>/")
def get_schedule(schedule_id):
    schedule = Schedule.query.get(schedule_id)
    if not schedule:
        return jsonify({"error": "Schedule not found"}), 404
    return jsonify(_serialize_schedule(schedule))


@main.delete("/schedules/<int:schedule_id>/offerings/")
def remove_schedule_offering(schedule_id): # course_id e.g. "MATH1920"
    payload = request.get_json(silent=True) or {}
    course_id = payload.get("course_id")
    offering_id = payload.get("offering_id")
    if offering_id is None and course_id is None:
        return jsonify({"error": "One of offering or course_id is required"}), 400

    sched = Schedule.query.filter_by(id=schedule_id).first()
    if sched is None:
        return jsonify({"error": "Schedule id invalid"}), 404
    
    if offering_id is None:
        offering = ( 
            CourseOffering.query
            .join(CachedCourse, CourseOffering.course_id == CachedCourse.id) .filter(
                CachedCourse.course_id == course_id,
                CourseOffering.semester == sched.semester,
                CourseOffering.component == "LEC",
            )
            .first()
        )
        offering = (CourseOffering.query # will need a refactor if CourseOffering.course_id is changed
            .join(CachedCourse, CourseOffering.course_id == CachedCourse.id) # CourseOffering.course_id references primary key of CachedCourse, not course code "CS2800"
            .join(ScheduleOffering, ScheduleOffering.offering_id == CourseOffering.id) 
            .filter(
                CachedCourse.course_id == course_id,
                ScheduleOffering.schedule_id == schedule_id,
                CourseOffering.component == "LEC",
            )
            .first()
        )
        if offering is None:
            return jsonify({"error": "Course not found for this semester"}), 404
        offering_id = offering.id
    # else offering_id is left as is

    removed = remove_schedule_offering_cascade(schedule_id=schedule_id, offering_id=offering_id)
    if removed == 0:
        return jsonify({"error": "Offering not found in schedule"}), 404
    return jsonify({"removed": removed}), 200


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
