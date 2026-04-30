from collections import defaultdict

DIST_MAP = {
    "SBA": {"SCD-AS", "SSC-AS", "D-AG"},
    "KCM": {"SMR-AS", "BIO-AS", "PHS-AS"},
    "LAD": {"ALC-AS", "LA-AG", "CA-AG", "HA-AG"}
}

def build_course_tags(session):
    from db import CachedCourse  # avoid circular imports

    tags_by_code = {}

    courses = session.query(CachedCourse).all()

    for c in courses:
        tags = set()
        dist = (c.distributions or "").upper()

        # map distributions → tags
        for key, values in DIST_MAP.items():
            if any(v in dist for v in values):
                tags.add(f"ENG_DIST_{key}")

        # CS 4000+
        if c.course_id.startswith("CS"):
            try:
                if int(c.course_id[2:]) >= 4000:
                    tags.add("CS_4000")
            except:
                pass

        tags_by_code[c.course_id] = tags

    return tags_by_code

try:
    from src.db import RequirementSet
except ModuleNotFoundError:
    from db import RequirementSet


def _rule_matches_course_code(rule, course_code: str, course_tags_by_code: dict[str, set[str]]) -> bool:
    if not course_code:
        return False

    code = course_code.strip().upper()
    tags = course_tags_by_code.get(code, set())

    for accepted in rule.accepted_courses:
        if accepted.course_id and accepted.course_id.strip().upper() == code:
            return True
        if accepted.course_tag and accepted.course_tag.strip().upper() in tags:
            return True
    return False


def evaluate_requirement_progress(user, completed_course_codes, planned_course_codes, course_credit_by_code, course_tags_by_code):
    """
    Compute requirement progress for the user's school + major.
    """
    completed_set = {code.upper() for code in completed_course_codes}
    planned_set = {code.upper() for code in planned_course_codes}

    req_sets = RequirementSet.query.filter(
        RequirementSet.scope.in_(["school", "major"])
    ).all()

    applicable_sets = []
    for req_set in req_sets:
        if req_set.scope == "school" and req_set.scope_key.lower() == (user.school or "").lower():
            if req_set.catalog_year in ("any", user.catalog_year):
                applicable_sets.append(req_set)
        if req_set.scope == "major" and req_set.scope_key.lower() == (user.major or "").lower():
            if req_set.catalog_year in ("any", user.catalog_year):
                applicable_sets.append(req_set)

    progress = []
    remaining_rule_ids = []
    group_progress = defaultdict(list)

    for req_set in applicable_sets:
        for rule in req_set.rules:
            matched_completed = sorted(
                [code for code in completed_set if _rule_matches_course_code(rule, code, course_tags_by_code)]
            )
            matched_planned = sorted(
                [
                    code for code in planned_set - completed_set
                    if _rule_matches_course_code(rule, code, course_tags_by_code)
                ]
            )

            satisfied = False
            if rule.rule_type == "required":
                satisfied = bool(matched_completed or matched_planned)
            elif rule.rule_type == "choose_n":
                satisfied = (len(matched_completed) + len(matched_planned)) >= (rule.n_required or 0)
            elif rule.rule_type == "credits_min":
                matched_codes = set(matched_completed + matched_planned)
                total_credits = sum(course_credit_by_code.get(code, 0) for code in matched_codes)
                satisfied = total_credits >= (rule.credits_min or 0)

            status = "satisfied" if satisfied else ("in_progress" if matched_planned else "remaining")
            if not satisfied:
                remaining_rule_ids.append(rule.id)

            payload = {
                "rule_id": rule.id,
                "scope": req_set.scope,
                "scope_key": req_set.scope_key,
                "title": rule.title,
                "group_id": rule.group_id,
                "rule_type": rule.rule_type,
                "status": status,
                "matched_completed": matched_completed,
                "matched_planned": matched_planned,
                "n_required": rule.n_required,
                "credits_min": rule.credits_min,
            }
            progress.append(payload)
            group_progress[(req_set.scope, req_set.scope_key, rule.group_id)].append(payload)

    grouped = []
    for (scope, scope_key, group_id), rules in group_progress.items():
        grouped.append(
            {
                "scope": scope,
                "scope_key": scope_key,
                "group_id": group_id,
                "rules": rules,
            }
        )

    return {
        "rules": progress,
        "groups": grouped,
        "remaining_rule_ids": remaining_rule_ids,
    }
