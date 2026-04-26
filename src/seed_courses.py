import time
import requests

from db import SessionLocal
from db import CachedCourse, CourseOffering

ROSTER = "FA26"
BASE_URL = "https://classes.cornell.edu/api/2.0"
REQUEST_DELAY = 1.1 


def safe_int(value, default=0):
    try:
        return int(float(value))
    except:
        return default


def get_subjects():
    """
    Fetch all subjects for FA26
    """
    url = f"{BASE_URL}/config/subjects.json"
    params = {"roster": ROSTER}

    response = requests.get(url, params=params)
    response.raise_for_status()

    data = response.json()

    return [item["value"] for item in data["data"]["subjects"]]


def get_classes_for_subject(subject):
    """
    Fetch all classes for a subject
    """
    url = f"{BASE_URL}/search/classes.json"

    params = {
        "roster": ROSTER,
        "subject": subject,
        "acadCareer[]": "UG"
    }

    response = requests.get(url, params=params)
    response.raise_for_status()

    return response.json()


def upsert_course(session, cls):
    """
    Insert/update CachedCourse
    """

    department = cls.get("subject", "").strip()
    course_number = cls.get("catalogNbr", "").strip()
    course_code = f"{department}{course_number}"

    existing = session.query(CachedCourse).filter_by(
        course_code=course_code
    ).first()

    title = (
        cls.get("titleLong")
        or cls.get("titleShort")
        or "Unknown Title"
    )

    credits = safe_int(
        cls.get("unitsMaximum")
        or cls.get("catalogCredits")
        or 0
    )

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
        existing.course_number = course_number
        existing.title = title
        existing.credits = credits
        existing.description = description
        existing.prerequisites = prerequisites
        existing.corequisites = corequisites
        existing.distributions = distributions

        return existing

    new_course = CachedCourse(
        course_code=course_code,
        department=department,
        course_number=course_number,
        title=title,
        credits=credits,
        description=description,
        prerequisites=prerequisites,
        corequisites=corequisites,
        distributions=distributions
    )

    session.add(new_course)
    session.flush()   

    return new_course


def insert_offerings(session, course_obj, cls):
    """
    Insert offerings for a course.
    Uses enrollGroups from Cornell API.
    """

    enroll_groups = cls.get("enrollGroups", [])

    for group in enroll_groups:
        section = str(group.get("classSections", "UNKNOWN"))

        meetings = group.get("meetings", [])

        if meetings:
            meeting = meetings[0]

            days = meeting.get("pattern", "")
            start_time = meeting.get("timeStart", "")
            end_time = meeting.get("timeEnd", "")
            location = meeting.get("facilityDescr", "")

            instructors = meeting.get("instructors", [])
            instructor = ""

            if instructors:
                instructor = instructors[0].get("firstName", "") + " " + instructors[0].get("lastName", "")
                instructor = instructor.strip()

        else:
            days = ""
            start_time = ""
            end_time = ""
            location = ""
            instructor = ""

        exists = session.query(CourseOffering).filter_by(
            course_id=course_obj.id,
            semester=ROSTER,
            section=section
        ).first()

        if exists:
            continue

        offering = CourseOffering(
            course_id=course_obj.id,
            semester=ROSTER,
            section=section,
            instructor=instructor,
            days=days,
            start_time=start_time,
            end_time=end_time,
            location=location
        )

        session.add(offering)

def seed():
    session = SessionLocal()

    subjects = get_subjects()
    print(f"Found {len(subjects)} subjects")

    total_courses = 0

    for subject in subjects:
        print(f"Importing {subject}...")

        try:
            payload = get_classes_for_subject(subject)
            classes = payload["data"]["classes"]

            for cls in classes:
                course_obj = upsert_course(session, cls)
                insert_offerings(session, course_obj, cls)
                total_courses += 1

            session.commit()

        except Exception as e:
            session.rollback()
            print(f"Failed {subject}: {e}")

        time.sleep(REQUEST_DELAY)

    session.close()

    print(f"Done. Imported approx {total_courses} classes.")


if __name__ == "__main__":
    seed()