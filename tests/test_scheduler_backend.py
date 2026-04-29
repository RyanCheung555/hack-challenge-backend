import unittest

from flask import Flask

from src.db import (
    CachedCourse,
    CompletedCourse,
    CourseOffering,
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
from src.services.scheduler import offerings_conflict


class SchedulerBackendTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        self.app = app
        db.init_app(self.app)
        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_requirement_progress_choose_n(self):
        with self.app.app_context():
            user = User(name="Test", school="engineering", major="CS", catalog_year="any", year=2)
            db.session.add(user)
            req_set = RequirementSet(scope="major", scope_key="CS", catalog_year="any")
            db.session.add(req_set)
            db.session.flush()

            rule = RequirementRule(
                requirement_set_id=req_set.id,
                group_id="cs_systems",
                rule_type="choose_n",
                n_required=2,
                title="Systems Electives",
            )
            db.session.add(rule)
            db.session.flush()

            db.session.add(RequirementCourse(requirement_rule_id=rule.id, course_id="CS3410"))
            db.session.add(RequirementCourse(requirement_rule_id=rule.id, course_id="CS4410"))
            db.session.add(RequirementCourse(requirement_rule_id=rule.id, course_id="CS4414"))
            db.session.commit()

            progress = evaluate_requirement_progress(
                user=user,
                completed_course_codes={"CS3410"},
                planned_course_codes={"CS4410"},
                course_credit_by_code={},
                course_tags_by_code={},
            )

            statuses = {row["title"]: row["status"] for row in progress["rules"]}
            self.assertEqual(statuses["Systems Electives"], "satisfied")

    def test_suggestions_filter_conflicts_and_prereqs(self):
        with self.app.app_context():
            user = User(name="Student", school="engineering", major="CS", catalog_year="any", year=1)
            db.session.add(user)
            db.session.flush()

            prereq_course = CachedCourse(
                course_id="MATH1910",
                department="MATH",
                number="1910",
                title="Calculus I",
                credits=4,
            )
            planned_course = CachedCourse(
                course_id="ENGRD2700",
                department="ENGRD",
                number="2700",
                title="Basic Engineering Probability",
                credits=4,
            )
            cs2110 = CachedCourse(
                course_id="CS2110",
                department="CS",
                number="2110",
                title="Object-Oriented Programming",
                credits=4,
                prerequisites="MATH 1910",
            )
            cs2800 = CachedCourse(
                course_id="CS2800",
                department="CS",
                number="2800",
                title="Discrete Structures",
                credits=4,
                prerequisites="PHYS 1112",
            )
            db.session.add_all([prereq_course, planned_course, cs2110, cs2800])
            db.session.flush()

            db.session.add(CompletedCourse(user_id=user.id, course_id=prereq_course.id))

            planned_offering = CourseOffering(
                course_id=planned_course.id,
                semester="FA26",
                section="001",
                days="TR",
                start_time="10:00AM",
                end_time="11:00AM",
            )
            candidate_ok = CourseOffering(
                course_id=cs2110.id,
                semester="FA26",
                section="001",
                days="MWF",
                start_time="01:25PM",
                end_time="02:15PM",
            )
            candidate_bad = CourseOffering(
                course_id=cs2800.id,
                semester="FA26",
                section="001",
                days="TR",
                start_time="10:30AM",
                end_time="11:20AM",
            )
            db.session.add_all([planned_offering, candidate_ok, candidate_bad])
            db.session.flush()

            schedule = Schedule(user_id=user.id, name="Draft", semester="FA26", status="active")
            db.session.add(schedule)
            db.session.flush()
            db.session.add(ScheduleOffering(schedule_id=schedule.id, offering_id=planned_offering.id))

            req_set = RequirementSet(scope="major", scope_key="CS", catalog_year="any")
            db.session.add(req_set)
            db.session.flush()
            rule = RequirementRule(
                requirement_set_id=req_set.id,
                group_id="cs_core",
                rule_type="required",
                title="CS Core",
            )
            db.session.add(rule)
            db.session.flush()
            db.session.add(RequirementCourse(requirement_rule_id=rule.id, course_id="CS2110"))
            db.session.add(RequirementCourse(requirement_rule_id=rule.id, course_id="CS2800"))
            db.session.commit()

            payload, status = build_suggestions_for_schedule(schedule.id, limit=10)
            self.assertEqual(status, 200)
            suggested_ids = {row["course_id"] for row in payload["suggestions"]}
            self.assertIn("CS2110", suggested_ids)
            self.assertNotIn("CS2800", suggested_ids)

    def test_time_overlap_utility(self):
        with self.app.app_context():
            c1 = CachedCourse(course_id="TEST1000", department="TEST", number="1000", title="A", credits=3)
            c2 = CachedCourse(course_id="TEST2000", department="TEST", number="2000", title="B", credits=3)
            db.session.add_all([c1, c2])
            db.session.flush()
            a = CourseOffering(course_id=c1.id, semester="FA26", section="001", days="MWF", start_time="09:05AM", end_time="09:55AM")
            b = CourseOffering(course_id=c2.id, semester="FA26", section="001", days="MWF", start_time="09:30AM", end_time="10:20AM")
            self.assertTrue(offerings_conflict(a, b))


if __name__ == "__main__":
    unittest.main()
