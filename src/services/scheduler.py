import re
from datetime import datetime


DAY_CHARS = set("MTWRFSU")


def parse_days(days_value: str) -> set[str]:
    if not days_value:
        return set()
    compact = re.sub(r"[^A-Za-z]", "", days_value.upper())
    return {char for char in compact if char in DAY_CHARS}


def parse_time_value(time_value: str):
    if not time_value:
        return None

    value = time_value.strip().upper().replace(" ", "")
    formats = ("%I:%M%p", "%I%p", "%H:%M", "%H%M")
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    return None


def offerings_conflict(offering_a, offering_b) -> bool:
    days_a = parse_days(offering_a.days or "")
    days_b = parse_days(offering_b.days or "")
    if not days_a.intersection(days_b):
        return False

    start_a = parse_time_value(offering_a.start_time or "")
    end_a = parse_time_value(offering_a.end_time or "")
    start_b = parse_time_value(offering_b.start_time or "")
    end_b = parse_time_value(offering_b.end_time or "")

    if not all([start_a, end_a, start_b, end_b]):
        return False

    return (start_a < end_b) and (start_b < end_a)


def has_conflict_with_schedule(candidate_offering, planned_offerings) -> bool:
    return any(offerings_conflict(candidate_offering, planned) for planned in planned_offerings)
