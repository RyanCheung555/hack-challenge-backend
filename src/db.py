from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# USERS
class User(db.Model):
    __tablename__ = "users"
    __table_args__ = (
        db.UniqueConstraint("name", "major", "year", name="uq_users_identity"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    school = db.Column(db.String, nullable=False, default="unknown")
    major = db.Column(db.String, nullable=False)
    catalog_year = db.Column(db.String, nullable=False, default="unknown")
    year = db.Column(db.Integer, nullable=False)
    netid = db.Column(db.String, nullable=False, unique=True)
    college = db.Column(db.String, nullable=False)
    target_term = db.Column(db.String, nullable=False)
    target_credits_low = db.Column(db.Integer, nullable=False)
    target_credits_high = db.Column(db.Integer, nullable=False)

    completed_courses = db.relationship(
        "CompletedCourse",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    schedules = db.relationship(
        "Schedule",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    distributions = db.relationship(
        "DistributionSet",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<User {self.id} {self.name} ({self.major} {self.year})>"


# MAJOR REQUIREMENTS
class MajorRequirement(db.Model):
    __tablename__ = "majors_requirements"
    __table_args__ = (
        db.UniqueConstraint(
            "major",
            "requirement_group",
            "requirement_type",
            "course_id",
            "group_id",
            name="uq_major_requirement_row",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    major = db.Column(db.String, nullable=False)
    requirement_group = db.Column(db.String, nullable=False)
    requirement_type = db.Column(db.String, nullable=False)
    course_id = db.Column(db.String, nullable=False)
    group_id = db.Column(db.String)

    def __repr__(self):
        return (
            f"<MajorRequirement {self.major} "
            f"{self.requirement_group} {self.requirement_type} {self.course_id}>"
        )

# CACHED COURSES
class CachedCourse(db.Model):
    __tablename__ = "cached_courses"

    id = db.Column(db.Integer, primary_key=True)

    course_id = db.Column(db.String, nullable=False, unique=True)
    department = db.Column(db.String, nullable=False)
    number = db.Column(db.String, nullable=False)

    title = db.Column(db.String, nullable=False)
    credits = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text)

    prerequisites = db.Column(db.Text)
    corequisites = db.Column(db.Text)
    distributions = db.Column(db.Text)
    offerings = db.relationship(
        "CourseOffering",
        back_populates="course",
        cascade="all, delete-orphan",
    )

    completed_by = db.relationship(
        "CompletedCourse",
        back_populates="course",
        cascade="all, delete-orphan",
    )
    tags = db.relationship("CourseTag", back_populates="course", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<CachedCourse {self.course_id} {self.title}>"


# COURSE OFFERINGS
class CourseOffering(db.Model):
    __tablename__ = "course_offerings"
    __table_args__ = (
        db.UniqueConstraint("semester", "class_nbr", name="uq_course_offerings_semester_class_nbr"),
    )

    id = db.Column(db.Integer, primary_key=True)

    course_id = db.Column(
        db.Integer,
        db.ForeignKey("cached_courses.id"),
        nullable=False,
    )

    semester = db.Column(db.String, nullable=False)
    class_nbr = db.Column(db.Integer, nullable=False)
    section = db.Column(db.String, nullable=False)
    component = db.Column(db.String)

    instructor = db.Column(db.String)
    days = db.Column(db.String)
    start_time = db.Column(db.String)
    end_time = db.Column(db.String)
    location = db.Column(db.String)

    course = db.relationship(
        "CachedCourse",
        back_populates="offerings",
    )

    planned_in = db.relationship(
        "ScheduleOffering",
        back_populates="offering",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return (
            f"<CourseOffering "
            f"{self.course.course_id} "
            f"{self.section} "
            f"{self.semester}>"
        )


# COMPLETED COURSES
class CompletedCourse(db.Model):
    __tablename__ = "completed_courses"
    __table_args__ = (
        db.UniqueConstraint("user_id", "course_id", name="uq_completed_courses_user_course"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("cached_courses.id"), nullable=False)

    user = db.relationship("User", back_populates="completed_courses")
    course = db.relationship("CachedCourse", back_populates="completed_by")


class Schedule(db.Model):
    __tablename__ = "schedules"
    __table_args__ = (
        db.UniqueConstraint("user_id", "semester", "name", name="uq_schedules_user_semester_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String, nullable=False, default="My Schedule")
    semester = db.Column(db.String, nullable=False)
    status = db.Column(db.String, nullable=False, default="active")

    user = db.relationship("User", back_populates="schedules")
    planned_offerings = db.relationship(
        "ScheduleOffering",
        back_populates="schedule",
        cascade="all, delete-orphan",
    )


class ScheduleOffering(db.Model):
    __tablename__ = "schedule_offerings"
    __table_args__ = (
        db.UniqueConstraint("schedule_id", "offering_id", name="uq_schedule_offerings_pair"),
    )

    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey("schedules.id"), nullable=False)
    offering_id = db.Column(db.Integer, db.ForeignKey("course_offerings.id"), nullable=False)

    schedule = db.relationship("Schedule", back_populates="planned_offerings")
    offering = db.relationship("CourseOffering", back_populates="planned_in")
    
def remove_schedule_offering_cascade(schedule_id: int, offering_id: int):
    """
    Delete a ScheduleOffering. If it's a LEC, also delete any associated DIS/LAB/PRJ rows in the schedule
    Returns the number of rows deleted (0 if nothing matched.) 
    """
    row = ScheduleOffering.query.filter_by(
        schedule_id=schedule_id, offering_id=offering_id
    ).first()
    if row is None:
        return 0

    deleted = 0
    offering = row.offering
    if (offering.component or "").upper() == "LEC":
        sibling_rows = (
            ScheduleOffering.query
            .join(CourseOffering, ScheduleOffering.offering_id == CourseOffering.id)
            .filter(
                ScheduleOffering.schedule_id == schedule_id,
                CourseOffering.course_id == offering.course_id,
                CourseOffering.semester == offering.semester,
                CourseOffering.component.in_(["DIS", "LAB", "PRJ"]),
                ScheduleOffering.id != row.id,
            )
            .all()
        )
        for s in sibling_rows:
            db.session.delete(s)
            deleted += 1
    db.session.delete(row)
    deleted += 1
    db.session.commit()
    return deleted

class DistributionSet(db.Model):
    __tablename__ = "distribution_sets"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    ALC = db.Column(db.Boolean, nullable=False) # boolean internally represented as 0/1
    BIO = db.Column(db.Boolean, nullable=False)
    ETM = db.Column(db.Boolean, nullable=False)
    GLC = db.Column(db.Boolean, nullable=False)
    HST = db.Column(db.Boolean, nullable=False)
    PHS = db.Column(db.Boolean, nullable=False)
    SCD = db.Column(db.Boolean, nullable=False)
    SSC = db.Column(db.Boolean, nullable=False)
    SDS = db.Column(db.Boolean, nullable=False)
    SMR = db.Column(db.Boolean, nullable=False)
    user = db.relationship("User", back_populates="distributions")
    DISTRIBUTION_FIELDS = ["ALC", "BIO", "ETM", "GLC", "HST", "PHS", "SCD", "SSC", "SDS","SMR"]
    @property
    def completed_distributions(self):  
        return [
            name for name in self.DISTRIBUTION_FIELDS
            if getattr(self, name, False)
        ] # e.g. {"BIO", "GLC"}

class RequirementSet(db.Model):
    __tablename__ = "requirement_sets"
    __table_args__ = (
        db.UniqueConstraint(
            "scope",
            "scope_key",
            "catalog_year",
            name="uq_requirement_sets_scope_key_catalog",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    scope = db.Column(db.String, nullable=False)  # school | major
    scope_key = db.Column(db.String, nullable=False)
    catalog_year = db.Column(db.String, nullable=False, default="any")

    rules = db.relationship(
        "RequirementRule",
        back_populates="requirement_set",
        cascade="all, delete-orphan",
    )


class RequirementRule(db.Model):
    __tablename__ = "requirement_rules"

    id = db.Column(db.Integer, primary_key=True)
    requirement_set_id = db.Column(
        db.Integer, db.ForeignKey("requirement_sets.id"), nullable=False
    )
    group_id = db.Column(db.String, nullable=False)
    rule_type = db.Column(db.String, nullable=False)  # required | choose_n | credits_min
    n_required = db.Column(db.Integer)
    credits_min = db.Column(db.Integer)
    title = db.Column(db.String, nullable=False)

    requirement_set = db.relationship("RequirementSet", back_populates="rules")
    accepted_courses = db.relationship(
        "RequirementCourse",
        back_populates="rule",
        cascade="all, delete-orphan",
    )


class RequirementCourse(db.Model):
    __tablename__ = "requirement_courses"
    __table_args__ = (
        db.UniqueConstraint(
            "requirement_rule_id",
            "course_id",
            "course_tag",
            name="uq_requirement_course_mapping",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    requirement_rule_id = db.Column(
        db.Integer, db.ForeignKey("requirement_rules.id"), nullable=False
    )
    course_id = db.Column(db.String)
    course_tag = db.Column(db.String)

    rule = db.relationship("RequirementRule", back_populates="accepted_courses")


class CourseTag(db.Model):
    __tablename__ = "course_tags"
    __table_args__ = (
        db.UniqueConstraint("course_id", "tag", name="uq_course_tags_pair"),
    )

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("cached_courses.id"), nullable=False)
    tag = db.Column(db.String, nullable=False)

    course = db.relationship("CachedCourse", back_populates="tags")


def init_db():
    db.create_all()


if __name__ == "__main__":
    from flask import Flask
    import os

    app = Flask(__name__)

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'courses.db')}"

    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    with app.app_context():
        init_db()
        print("Database tables created.")