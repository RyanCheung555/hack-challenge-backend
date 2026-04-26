from flask import Blueprint

main = Blueprint("main", __name__)


@main.get("/")
def health_check() -> str:
    return "CourseFinderBackend is running."
