import re

from sqlalchemy.orm import joinedload

try:
    from src.db import (
        CachedCourse,
        CompletedCourse,
        CourseOffering,
        RequirementRule,
        Schedule,
        ScheduleOffering,
        db,
    )
    from src.services.requirements import evaluate_requirement_progress
    from src.services.scheduler import has_conflict_with_schedule
except ModuleNotFoundError:
    from db import (
        CachedCourse,
        CompletedCourse,
        CourseOffering,
        RequirementRule,
        Schedule,
        ScheduleOffering,
        db,
    )
    from services.requirements import evaluate_requirement_progress
    from services.scheduler import has_conflict_with_schedule


COURSE_CODE_PATTERN = re.compile(r"\b([A-Z]{2,4}\s?\d{4})\b")


def extract_course_codes(text_value: str) -> set[str]:
    if not text_value:
        return set()
    return {match.replace(" ", "").upper() for match in COURSE_CODE_PATTERN.findall(text_value.upper())}


def _course_maps():
    courses = CachedCourse.query.options(joinedload(CachedCourse.tags)).all()
    credit_by_code = {}
    tags_by_code = {}
    for course in courses:
        code = (course.course_id or "").upper()
        if not code:
            continue
        credit_by_code[code] = course.credits or 0
        tags_by_code[code] = {tag.tag.upper() for tag in course.tags}
    return credit_by_code, tags_by_code


def _rule_matches_offering(rule, offering, course_tags_by_code):
    course_code = offering.course.course_id.upper()
    tags = course_tags_by_code.get(course_code, set())
    for accepted in rule.accepted_courses:
        if accepted.course_id and accepted.course_id.upper() == course_code:
            return True
        if accepted.course_tag and accepted.course_tag.upper() in tags:
            return True
    return False


def _prereqs_satisfied(offering, completed_codes, planned_codes):
    required_codes = extract_course_codes(offering.course.prerequisites or "")
    if not required_codes:
        return True
    return required_codes.issubset(completed_codes.union(planned_codes))


def build_suggestions_for_schedule(schedule_id: int, limit: int = 25):
    schedule = db.session.get(
        Schedule,
        schedule_id,
        options=[
            joinedload(Schedule.user),
            joinedload(Schedule.planned_offerings)
            .joinedload(ScheduleOffering.offering)
            .joinedload(CourseOffering.course),
        ],
    )
    if not schedule:
        return {"error": "Schedule not found"}, 404

    planned_offerings = [row.offering for row in schedule.planned_offerings]
    planned_codes = {off.course.course_id.upper() for off in planned_offerings}

    completed_rows = CompletedCourse.query.options(joinedload(CompletedCourse.course)).filter_by(
        user_id=schedule.user_id
    ).all()
    completed_codes = {row.course.course_id.upper() for row in completed_rows}

    credit_by_code, tags_by_code = _course_maps()
    progress = evaluate_requirement_progress(
        schedule.user,
        completed_codes,
        planned_codes,
        credit_by_code,
        tags_by_code,
    )

    remaining_rule_ids = progress["remaining_rule_ids"]
    unmet_rules = RequirementRule.query.options(joinedload(RequirementRule.accepted_courses)).filter(
        RequirementRule.id.in_(remaining_rule_ids)
    ).all() if remaining_rule_ids else []

    query = CourseOffering.query.options(joinedload(CourseOffering.course)).filter_by(semester=schedule.semester)
    candidates = []
    for offering in query.all():
        course_code = offering.course.course_id.upper()
        if course_code in completed_codes or course_code in planned_codes:
            continue
        if has_conflict_with_schedule(offering, planned_offerings):
            continue
        if not _prereqs_satisfied(offering, completed_codes, planned_codes):
            continue

        matched_rules = [rule for rule in unmet_rules if _rule_matches_offering(rule, offering, tags_by_code)]
        if not matched_rules:
            continue

        priority = 2
        if any(rule.rule_type == "required" for rule in matched_rules):
            priority = 0
        elif any(rule.rule_type == "choose_n" for rule in matched_rules):
            priority = 1

        candidates.append(
            {
                "offering_id": offering.id,
                "course_id": offering.course.course_id,
                "title": offering.course.title,
                "semester": offering.semester,
                "section": offering.section,
                "instructor": offering.instructor,
                "days": offering.days,
                "start_time": offering.start_time,
                "end_time": offering.end_time,
                "location": offering.location,
                "priority": priority,
                "reason_codes": [rule.rule_type for rule in matched_rules],
                "satisfies": [
                    {
                        "rule_id": rule.id,
                        "title": rule.title,
                        "group_id": rule.group_id,
                        "rule_type": rule.rule_type,
                    }
                    for rule in matched_rules
                ],
                "conflicts_with": [],
            }
        )

    candidates.sort(key=lambda row: (row["priority"], row["course_id"], row["section"]))
    return {"schedule_id": schedule.id, "suggestions": candidates[:limit], "progress": progress}, 200
