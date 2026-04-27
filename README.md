# CourseFinderBackend

Minimal Flask starter backend.

## Setup

Setup:
1. python3 -m venv venv
2. source venv/bin/activate
3. python src/db.py
4. python src/seed_courses.py (you only need to run 3 and 4 once)
5. python run.py

App will start on `http://127.0.0.1:8000/`.

## Database Design

Backend Proposed Schema:  

1. users  
id: int  
name: str  
major: str  
year: int  

2. completed_courses  
user_id: int, FK -> User  
course_id: int, FK -> CachedCourse  

3. schedules  
id: int  
user_id: int, FK -> User  
planned_offerings: relationship -> CourseOffering via a table (schedules.id, course_offerings.id)  

4. majors_requirements  
id: int  
major: str  
requirement_group: str  
requirement_type: str  
course_id: str  
group_id: str  

5. cached_courses  
Static course info.  
id: int  
course_code: int  
department: str  
course_number: int  
title: str  
credits: int  
description: str  
prerequisites: str  
corequisites: str  
distributions: str  
offerings: relationship -> CourseOffering.course  

6. course_offerings  
id: int  
course_id: int, FK -> CachedCourse  
semester: str  
section: str  
instructor: str  
days: str  
start_time: str  
end_time: str  
location: str  
course: relationship => CachedCourse.offerings  



