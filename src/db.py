from sqlalchemy import Column, Integer, String, Text, ForeignKey, create_engine, Table
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

DATABASE_URL = "sqlite:///courses.db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()

# COMPLETED COURSES

class CompletedCourse(Base):
    __tablename__ = "completed_courses"

    # avoid duplicate course/user pairs
    user_id = Column(ForeignKey("users.id"), primary_key=True)
    course_id = Column(ForeignKey("cached_courses.course_id"), primary_key=True) 
    # Add a way to e.g. designate CS2112 as completed with CS2110 in major requirements

schedule_offerings_table = Table(
    "schedule_offerings",
    Base.metadata,
    Column("schedule_id", ForeignKey("schedules.id"), primary_key=True),
    Column("offering_id", ForeignKey("course_offerings.id"), primary_key=True),
)

class Schedule(Base):
    __tablename__ = "schedules"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey("users.id")) 
    planned_offerings = relationship( # planned courses
        "CourseOffering",
        secondary=schedule_offerings_table) 
    # for pcourse in schedule.planned_courses -> pcourse is a CourseOffering
    # you can access pcourse.course_id for example

# CACHED COURSES

class CachedCourse(Base):
    __tablename__ = "cached_courses"

    id = Column(Integer, primary_key=True)

    course_code = Column(String, nullable=False, unique=True)   
    department = Column(String, nullable=False)                
    course_number = Column(String, nullable=False)            

    title = Column(String, nullable=False)
    credits = Column(Integer, nullable=False)
    description = Column(Text)

    prerequisites = Column(Text)
    corequisites = Column(Text)
    distributions = Column(Text)

    offerings = relationship(
        "CourseOffering",
        back_populates="course",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<CachedCourse {self.course_code} {self.title}>"


# COURSE OFFERINGS

class CourseOffering(Base):
    __tablename__ = "course_offerings"

    id = Column(Integer, primary_key=True)

    course_id = Column(
        Integer,
        ForeignKey("cached_courses.id"),
        nullable=False
    )

    semester = Column(String, nullable=False)     
    section = Column(String, nullable=False)      

    instructor = Column(String)
    days = Column(String)                        
    start_time = Column(String)                 
    end_time = Column(String)                    
    location = Column(String)

    # Many offerings -> one course
    course = relationship(
        "CachedCourse",
        back_populates="offerings"
    )

    def __repr__(self):
        return (
            f"<CourseOffering "
            f"{self.course.course_code} "
            f"{self.section} "
            f"{self.semester}>"
        )
    
def init_db():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db()
    print("Database tables created.")