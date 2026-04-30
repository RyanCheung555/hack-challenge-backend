import time

from services.cornell_api import get_subjects, get_classes_for_subject
from app import create_app
from db import CachedCourse, CourseOffering, db

ROSTER = "FA26"
REQUEST_DELAY = 1.1


def safe_int(value, default=0):
    try:
        return int(float(value))
    except:
        return default


def derive_credits_from_sections(cls):
    """
    Fallback credit heuristic when Cornell catalog credit fields are null.
    Rule:
      - If a course has LEC plus any other component (DIS/LAB/PRJ/etc), use 4.
      - Otherwise use 3.
    """
    enroll_groups = cls.get("enrollGroups", [])
    has_lecture = False
    has_non_lecture = False

    for group in enroll_groups:
        class_sections = group.get("classSections", [])
        for section in class_sections:
            component = (section.get("ssrComponent") or "").strip().upper()
            if component == "LEC":
                has_lecture = True
            elif component:
                has_non_lecture = True

    if has_lecture and has_non_lecture:
        return 4
    return 3


def upsert_course(session, cls):
    """
    Insert/update CachedCourse
    """

    department = cls.get("subject", "").strip()
    course_number = cls.get("catalogNbr", "").strip()
    course_code = f"{department}{course_number}"

    existing = session.query(CachedCourse).filter_by(
        course_id=course_code
    ).first()

    title = (
        cls.get("titleLong")
        or cls.get("titleShort")
        or "Unknown Title"
    )

    credits = safe_int(
        cls.get("catalogCredits")
        or cls.get("unitsMaximum")
        or 0
    )
    if credits <= 0:
        credits = derive_credits_from_sections(cls)

    description = cls.get("description") or ""

    prerequisites = (
        cls.get("catalogPrereq")
        or cls.get("catalogPrereqCoreq")
        or ""
    )

    corequisites = cls.get("catalogCoreq") or ""

    distributions = ""
    attr_groups = cls.get("crseAttrValueGroups", [])

    if attr_groups:
        vals = []
        for item in attr_groups:
            if item.get("attrDescr") == "Distribution Requirements":
                vals.append(item.get("crseAttrValues", ""))
        distributions = "; ".join(vals)

    if existing:
        existing.department = department
        existing.number = course_number
        existing.title = title
        existing.credits = credits
        existing.description = description
        existing.prerequisites = prerequisites
        existing.corequisites = corequisites
        existing.distributions = distributions

        return existing

    new_course = CachedCourse(
        course_id=course_code,
        department=department,
        number=course_number,
        title=title,
        credits=credits,
        description=description,
        prerequisites=prerequisites,
        corequisites=corequisites,
        distributions=distributions,
    )

    session.add(new_course)
    session.flush()   

    return new_course


def insert_offerings(session, course_obj, cls):
    """
    Insert offerings for a course.
    Uses enrollGroups -> classSections -> meetings
    """

    enroll_groups = cls.get("enrollGroups", [])

    for group in enroll_groups:
        class_sections = group.get("classSections", [])

        for sec in class_sections:
            section = sec.get("section", "UNKNOWN")
            component = sec.get("ssrComponent", "")
            class_nbr = safe_int(sec.get("classNbr"), default=0)
            if not class_nbr:
                continue

            meetings = sec.get("meetings", [])

            if meetings:
                meeting = meetings[0]

                days = meeting.get("pattern", "")
                start_time = meeting.get("timeStart", "")
                end_time = meeting.get("timeEnd", "")
                location = meeting.get("facilityDescr", "")

                instructors = meeting.get("instructors", [])
                instructor = ""

                if instructors:
                    instructor = (
                        instructors[0].get("firstName", "") + " " +
                        instructors[0].get("lastName", "")
                    ).strip()
            else:
                days = ""
                start_time = ""
                end_time = ""
                location = ""
                instructor = ""

            # prevent duplicates
            exists = session.query(CourseOffering).filter_by(
                semester=ROSTER,
                class_nbr=class_nbr,
            ).first()

            if exists:
                exists.course_id = course_obj.id
                exists.section = section
                exists.component = component
                exists.instructor = instructor
                exists.days = days
                exists.start_time = start_time
                exists.end_time = end_time
                exists.location = location
                continue

            offering = CourseOffering(
                course_id=course_obj.id,
                semester=ROSTER,
                class_nbr=class_nbr,
                section=section,
                component=component,
                instructor=instructor,
                days=days,
                start_time=start_time,
                end_time=end_time,
                location=location
            )

            session.add(offering)

def seed():
    subjects = get_subjects(ROSTER)
    print(f"Found {len(subjects)} subjects")

    total_courses = 0

    for subject in subjects:
        print(f"Importing {subject}...")

        try:
            payload = get_classes_for_subject(ROSTER, subject)
            classes = payload["data"]["classes"]

            for cls in classes:
                course_obj = upsert_course(db.session, cls)
                insert_offerings(db.session, course_obj, cls)
                total_courses += 1

            db.session.commit()

        except Exception as e:
            db.session.rollback()
            print(f"Failed {subject}: {e}")

        time.sleep(REQUEST_DELAY)

    print(f"Done. Imported approx {total_courses} classes.")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed()