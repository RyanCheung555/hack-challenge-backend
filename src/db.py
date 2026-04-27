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
    major = db.Column(db.String, nullable=False)
    year = db.Column(db.Integer, nullable=False)

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

    def __repr__(self):
        return f"<CachedCourse {self.course_id} {self.title}>"


# COURSE OFFERINGS
class CourseOffering(db.Model):
    __tablename__ = "course_offerings"

    id = db.Column(db.Integer, primary_key=True)

    course_id = db.Column(
        db.Integer,
        db.ForeignKey("cached_courses.id"),
        nullable=False,
    )

    semester = db.Column(db.String, nullable=False)
    section = db.Column(db.String, nullable=False)

    instructor = db.Column(db.String)
    days = db.Column(db.String)
    start_time = db.Column(db.String)
    end_time = db.Column(db.String)
    location = db.Column(db.String)

    course = db.relationship(
        "CachedCourse",
        back_populates="offerings",
    )

    scheduled_by = db.relationship("Schedule", back_populates="offering", cascade="all, delete-orphan")

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
        db.UniqueConstraint("user_id", "offering_id", name="uq_schedules_user_offering"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    offering_id = db.Column(db.Integer, db.ForeignKey("course_offerings.id"), nullable=False)

    user = db.relationship("User", back_populates="schedules")
    offering = db.relationship("CourseOffering", back_populates="scheduled_by")


def init_db():
    db.create_all()


if __name__ == "__main__":
    from flask import Flask

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///courses.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    with app.app_context():
        init_db()
        print("Database tables created.")