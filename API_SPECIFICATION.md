# Course Planner API Specification

Base URL: `http://127.0.0.1:5000`

All requests and responses use JSON.

Routes below mirror the Postman collection (`CourseFinderBackend Local`).

---

## 1. Health Check

Route:
GET /

Example:
```
http://127.0.0.1:5000/
GET
```

Success response 200 (plain text, not JSON):
```
CourseFinderBackend is running.
```

---

## 2. Create User

Route:
POST /users/

Required fields:
name
netid (unique)
major
school
college
year (int)
targetTerm
targetCreditsLow (int)
targetCreditsHigh (int)

Example:
```
http://127.0.0.1:5000/users/
POST
{
  "name": "Avery Chen",
  "netid": "ac2847",
  "major": "CS",
  "school": "engineering",
  "college": "Engineering",
  "year": 2,
  "targetTerm": "Fall 2026",
  "targetCreditsLow": 13,
  "targetCreditsHigh": 17
}
```

Success response 201:
```json
{
  "id": 1,
  "name": "Avery Chen",
  "initial": "AC",
  "netid": "ac2847",
  "school": "engineering",
  "college": "Engineering",
  "major": "CS",
  "completed_distributions": [],
  "catalog_year": "any",
  "year": 2,
  "target_term": "Fall 2026",
  "target_credits_low": 13,
  "target_credits_high": 17,
  "completed": []
}
```

Save the returned id as userId.

Missing fields 400:
```json
{
  "error": "Missing required fields: name, major, targetTerm"
}
```

Invalid credit range 400:
```json
{
  "error": "target_credits_low cannot exceed target_credits_high"
}
```

Conflict response 409 (netid already exists):
```json
{
  "error": "User with this netid already exists",
  "user_id": 1,
  "netid": "ac2847"
}
```

---

## 3. List Users

Route:
GET /users/

Example:
```
http://127.0.0.1:5000/users/
GET
```

Success response 200:
```json
[
  {
    "id": 1,
    "name": "Avery Chen",
    "initial": "AC",
    "netid": "ac2847",
    "school": "engineering",
    "college": "Engineering",
    "major": "CS",
    "completed_distributions": ["ALC", "BIO"],
    "catalog_year": "any",
    "year": 2,
    "target_term": "Fall 2026",
    "target_credits_low": 13,
    "target_credits_high": 17,
    "completed": ["CS1110", "MATH1910"]
  }
]
```

---

## 4. List Courses

Route:
GET /courses

Example:
```
http://127.0.0.1:5000/courses
GET
```

Success response 200 (each entry includes its offerings; if no `semester` filter, `open` is true when any offering exists):
```json
[
  {
    "id": 42,
    "courseId": "CS1110",
    "name": "Introduction to Computing Using Python",
    "department": "CS",
    "courseNumber": "1110",
    "credits": 4,
    "description": "Programming and problem solving using Python...",
    "prerequisites": null,
    "corequisites": null,
    "distributions": "(SMR-AS)",
    "tags": ["ENG_DIST_KCM"],
    "offerings": [
      {
        "id": 2156,
        "semester": "FA26",
        "classNbr": 17236,
        "section": "001",
        "component": "LEC",
        "instructor": "Anne Bracy",
        "days": "TR",
        "startTime": "11:25AM",
        "endTime": "12:40PM",
        "time": "11:25AM-12:40PM",
        "location": "Statler Hall 185"
      }
    ],
    "open": true
  }
]
```

---

## 5. List Courses (filtered)

Route:
GET /courses

Query params (all optional):
semester (e.g. FA26 — also restricts the embedded offerings to that term)
q (search query against course_id, title, or description, e.g. intro)
subject (department code, e.g. CS)
credits (int, e.g. 4)

Example:
```
http://127.0.0.1:5000/courses?semester=FA26&q=intro&subject=CS&credits=4
GET
```

Success response 200:
Same shape as List Courses (above). When `semester` is provided, only courses with at least one offering in that term are returned and only that term's offerings appear in the `offerings` array.

---

## 6. Get Course By ID

Route:
GET /courses/<courseId>

Query params (optional):
semester (filter embedded offerings to that term)

Example:
```
http://127.0.0.1:5000/courses/CS1110
GET
```

Success response 200:
```json
{
  "id": 42,
  "courseId": "CS1110",
  "name": "Introduction to Computing Using Python",
  "department": "CS",
  "courseNumber": "1110",
  "credits": 4,
  "description": "Programming and problem solving using Python...",
  "prerequisites": null,
  "corequisites": null,
  "distributions": "(SMR-AS)",
  "tags": ["ENG_DIST_KCM"],
  "offerings": [
    {
      "id": 2156,
      "semester": "FA26",
      "classNbr": 17236,
      "section": "001",
      "component": "LEC",
      "instructor": "Anne Bracy",
      "days": "TR",
      "startTime": "11:25AM",
      "endTime": "12:40PM",
      "time": "11:25AM-12:40PM",
      "location": "Statler Hall 185"
    }
  ],
  "open": true
}
```

Course not found 404:
```json
{
  "error": "Course not found"
}
```

---

## 7. List Course Semesters

Route:
GET /courses/semesters

Example:
```
http://127.0.0.1:5000/courses/semesters
GET
```

Success response 200:
```json
{
  "semesters": ["FA25", "SP26", "FA26"]
}
```

---

## 8. Add Completed Course

Route:
POST /users/<userId>/completed-courses/

Body:
course_id (e.g. CS1110, MATH1910)

Example:
```
http://127.0.0.1:5000/users/1/completed-courses/
POST
{
  "course_id": "CS1110"
}
```

Success response 201:
```json
{
  "user_id": 1,
  "course_id": "CS1110"
}
```

Already exists 200:
```json
{
  "message": "Course already marked completed"
}
```

Missing course_id 400:
```json
{
  "error": "Missing required field: course_id"
}
```

User not found 404:
```json
{
  "error": "User not found"
}
```

Cached course not found 404:
```json
{
  "error": "Cached course not found"
}
```

---

## 9. Create Schedule

Route:
POST /users/<userId>/schedules/

Body:
semester (e.g. FA26)
name

Example:
```
http://127.0.0.1:5000/users/1/schedules/
POST
{
  "semester": "FA26",
  "name": "My Schedule"
}
```

Success response 201:
```json
{
  "id": 1,
  "user_id": 1,
  "name": "My Schedule",
  "semester": "FA26",
  "status": "active"
}
```

Save returned id as scheduleId.

Missing semester 400:
```json
{
  "error": "Missing required field: semester"
}
```

User not found 404:
```json
{
  "error": "User not found"
}
```

---

## 10. List User Schedules

Route:
GET /users/<userId>/schedules/

Query params (optional):
semester (filter to one term, e.g. FA26)

Example:
```
http://127.0.0.1:5000/users/1/schedules/?semester=FA26
GET
```

Success response 200:
```json
{
  "schedules": [
    {
      "id": 1,
      "user_id": 1,
      "name": "My Schedule",
      "semester": "FA26",
      "status": "active",
      "planned_count": 2
    }
  ]
}
```

User not found 404:
```json
{
  "error": "User not found"
}
```

---

## 11. Get Schedule

Route:
GET /schedules/<scheduleId>/

Example:
```
http://127.0.0.1:5000/schedules/1/
GET
```

Success response 200:
```json
{
  "id": 1,
  "user_id": 1,
  "name": "My Schedule",
  "semester": "FA26",
  "status": "active",
  "planned_offerings": [
    {
      "id": 2156,
      "offering_id": 2156,
      "course_code": "CS2110",
      "semester": "FA26",
      "classNbr": 17236,
      "section": "001",
      "component": "LEC",
      "instructor": "Anne Bracy",
      "days": "TR",
      "startTime": "11:25AM",
      "endTime": "12:40PM",
      "time": "11:25AM-12:40PM",
      "location": "Statler Hall 185"
    },
    {
      "id": 2158,
      "offering_id": 2158,
      "course_code": "CS2110",
      "semester": "FA26",
      "classNbr": 17240,
      "section": "201",
      "component": "DIS",
      "instructor": "TA Staff",
      "days": "F",
      "startTime": "2:30PM",
      "endTime": "3:20PM",
      "time": "2:30PM-3:20PM",
      "location": "Hollister Hall 320"
    }
  ]
}
```

Schedule not found 404:
```json
{
  "error": "Schedule not found"
}
```

---

## 12. Add Offering To Schedule

Route:
POST /schedules/<scheduleId>/offerings/

Body (use one):
class_nbr (recommended; Cornell class number from roster data for that term)
offering_id (internal DB id)

Behavior:
If selected offering is a lecture (LEC), backend auto-adds the first valid non-conflicting section for each non-LEC component type (e.g. DIS, PRJ). Response includes added_offering_ids (lecture + auto-added sections) and the full planned_offerings list after the add.

Example (recommended, class_nbr):
```
http://127.0.0.1:5000/schedules/1/offerings/
POST
{
  "class_nbr": 17236
}
```

Example (offering_id):
```
http://127.0.0.1:5000/schedules/1/offerings/
POST
{
  "offering_id": 2156
}
```

Success response 201:
```json
{
  "schedule_id": 1,
  "added_offering_ids": [2156, 2158],
  "planned_offerings": [
    {
      "offering_id": 2156,
      "course_id": "CS2110",
      "component": "LEC",
      "section": "001"
    },
    {
      "offering_id": 2158,
      "course_id": "CS2110",
      "component": "DIS",
      "section": "201"
    }
  ]
}
```

Already in schedule 200:
```json
{
  "message": "Offering already in schedule"
}
```

Conflict with existing schedule 409:
```json
{
  "error": "Offering conflicts with existing schedule"
}
```

No valid section for a required component 409 (component is the missing type, e.g. DIS, PRJ):
```json
{
  "error": "No valid DIS section available for this lecture",
  "offering_id": 2156
}
```

Missing input 400:
```json
{
  "error": "One of offering_id or class_nbr is required"
}
```

Schedule not found 404:
```json
{
  "error": "Schedule not found"
}
```

Offering not found 404:
```json
{
  "error": "Offering not found"
}
```

---

## 13. Get Progress

Route:
GET /users/<userId>/progress/

Query params:
schedule_id (optional; when provided, planned offerings in that schedule count toward in_progress status)

Example:
```
http://127.0.0.1:5000/users/1/progress/?schedule_id=1
GET
```

Status mapping for frontend enum:
satisfied -> COMPLETE
in_progress -> IN_PROGRESS
remaining -> MISSING

rule_type values: required, choose_n, credits_min

Note: each rule object in `groups[].rules` has the same shape as in the top-level `rules` array (the same payload object is reused — `scope` and `scope_key` are present there too).

Success response 200 (trimmed):
```json
{
  "rules": [
    {
      "rule_id": 9,
      "scope": "major",
      "scope_key": "CS",
      "title": "Intro CS",
      "group_id": "cs_intro",
      "rule_type": "choose_n",
      "status": "satisfied",
      "matched_completed": ["CS1110"],
      "matched_planned": [],
      "n_required": 1,
      "credits_min": null
    },
    {
      "rule_id": 10,
      "scope": "major",
      "scope_key": "CS",
      "title": "OOP",
      "group_id": "cs_oop",
      "rule_type": "choose_n",
      "status": "in_progress",
      "matched_completed": [],
      "matched_planned": ["CS2110"],
      "n_required": 1,
      "credits_min": null
    }
  ],
  "groups": [
    {
      "scope": "major",
      "scope_key": "CS",
      "group_id": "cs_intro",
      "rules": [
        {
          "rule_id": 9,
          "scope": "major",
          "scope_key": "CS",
          "title": "Intro CS",
          "group_id": "cs_intro",
          "rule_type": "choose_n",
          "status": "satisfied",
          "matched_completed": ["CS1110"],
          "matched_planned": [],
          "n_required": 1,
          "credits_min": null
        }
      ]
    }
  ],
  "remaining_rule_ids": [10, 11, 12]
}
```

User not found 404:
```json
{
  "error": "User not found"
}
```

Schedule does not belong to this user (or doesn't exist) 404:
```json
{
  "error": "Schedule not found for user"
}
```

---

## 14. Get Suggestions

Route:
GET /schedules/<scheduleId>/suggestions/

Query params:
limit (default 25)

Example:
```
http://127.0.0.1:5000/schedules/1/suggestions/?limit=25
GET
```

What this includes:
unmet-requirement-driven suggestions, LEC components only
excludes already completed/planned courses
excludes offerings conflicting with current planned schedule
sorted by catalog number, then course_id, then section

priority values: 0 (matches a `required` rule), 1 (matches a `choose_n` rule), 2 (otherwise)

The `progress` field contains the full progress payload (same shape as endpoint 13).

Success response 200 (trimmed):
```json
{
  "schedule_id": 1,
  "suggestions": [
    {
      "offering_id": 7032,
      "course_id": "PHYS1116",
      "course_number": "1116",
      "title": "Physics I: Mechanics and Special Relativity",
      "semester": "FA26",
      "section": "001",
      "instructor": "Maxim Perelstein",
      "days": "MWF",
      "start_time": "10:10AM",
      "end_time": "11:00AM",
      "location": "Rockefeller Hall 201",
      "priority": 1,
      "reason_codes": ["choose_n"],
      "satisfies": [
        {
          "rule_id": 6,
          "title": "Physics Sequence",
          "group_id": "physics",
          "rule_type": "choose_n"
        }
      ],
      "conflicts_with": []
    }
  ],
  "progress": {
    "rules": [ /* same shape as endpoint 13 */ ],
    "groups": [ /* same shape as endpoint 13 */ ],
    "remaining_rule_ids": [6, 7, 10]
  }
}
```

Schedule not found 404:
```json
{
  "error": "Schedule not found"
}
```

---

## 15. Remove Offering From Schedule

Route:
DELETE /schedules/<scheduleId>/offerings/

Body (use one):
course_id (recommended, e.g. CS1110 — removes the LEC and cascades to its attached sections)
offering_id (internal DB id)

Example (recommended, course_id):
```
http://127.0.0.1:5000/schedules/1/offerings/
DELETE
{
  "course_id": "CS1110"
}
```

Example (offering_id):
```
http://127.0.0.1:5000/schedules/1/offerings/
DELETE
{
  "offering_id": 2156
}
```

Success response 200 (removed = number of schedule_offerings rows removed by the cascade):
```json
{
  "removed": 2
}
```

Missing input 400:
```json
{
  "error": "One of offering or course_id is required"
}
```

Schedule not found 404:
```json
{
  "error": "Schedule id invalid"
}
```

Course not found in this semester 404:
```json
{
  "error": "Course not found for this semester"
}
```

Offering not in schedule 404:
```json
{
  "error": "Offering not found in schedule"
}
```

---

## Typical frontend call sequence

POST /users/ (or restore via GET /users/)  
POST /users/<id>/completed-courses/ (repeat for onboarding completions)  
POST /users/<id>/schedules/  
GET /users/<id>/progress/?schedule_id=...  
GET /schedules/<id>/suggestions/  
On "add class" action: POST /schedules/<id>/offerings/ with class_nbr  
On "remove class" action: DELETE /schedules/<id>/offerings/ with course_id  
Re-fetch progress + suggestions after schedule changes  
