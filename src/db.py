from sqlalchemy import Column, Integer, String, Text, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

DATABASE_URL = "sqlite:///courses.db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()


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