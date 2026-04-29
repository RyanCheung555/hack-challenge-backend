import json
import os

from app import create_app
from db import RequirementCourse, RequirementRule, RequirementSet, db


def seed_requirement_rules():
    base_dir = os.path.dirname(__file__)
    requirements_path = os.path.join(base_dir, "data", "requirements_v1.json")
    with open(requirements_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    for req_set in payload.get("requirement_sets", []):
        req_set_row = RequirementSet.query.filter_by(
            scope=req_set["scope"],
            scope_key=req_set["scope_key"],
            catalog_year=req_set.get("catalog_year", "any"),
        ).first()
        if not req_set_row:
            req_set_row = RequirementSet(
                scope=req_set["scope"],
                scope_key=req_set["scope_key"],
                catalog_year=req_set.get("catalog_year", "any"),
            )
            db.session.add(req_set_row)
            db.session.flush()

        for rule in req_set.get("rules", []):
            rule_row = RequirementRule.query.filter_by(
                requirement_set_id=req_set_row.id,
                group_id=rule["group_id"],
                rule_type=rule["rule_type"],
                title=rule["title"],
            ).first()
            if not rule_row:
                rule_row = RequirementRule(
                    requirement_set_id=req_set_row.id,
                    group_id=rule["group_id"],
                    rule_type=rule["rule_type"],
                    n_required=rule.get("n_required"),
                    credits_min=rule.get("credits_min"),
                    title=rule["title"],
                )
                db.session.add(rule_row)
                db.session.flush()

            for course_code in rule.get("courses", []):
                exists = RequirementCourse.query.filter_by(
                    requirement_rule_id=rule_row.id,
                    course_id=course_code,
                    course_tag=None,
                ).first()
                if not exists:
                    db.session.add(
                        RequirementCourse(
                            requirement_rule_id=rule_row.id,
                            course_id=course_code,
                        )
                    )

            for tag in rule.get("tags", []):
                exists = RequirementCourse.query.filter_by(
                    requirement_rule_id=rule_row.id,
                    course_id=None,
                    course_tag=tag,
                ).first()
                if not exists:
                    db.session.add(
                        RequirementCourse(
                            requirement_rule_id=rule_row.id,
                            course_tag=tag,
                        )
                    )

    db.session.commit()
    print("Requirement rules seeded.")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed_requirement_rules()
