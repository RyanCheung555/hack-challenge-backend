from flask import Flask

try:
    from src.db import db, init_db
    from src.routes.routes import main
except ModuleNotFoundError:
    from db import db, init_db
    from routes.routes import main


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///courses.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        init_db()

    app.register_blueprint(main)
    return app

# This needs merging with other backend initialization, wasn't sure how to do so
# Completed Courses and Schedule Routes

# import json
# import os

# from db import CompletedCourse, CourseOffering, Schedule, db, User
# from flask import Flask, request

# app = Flask(__name__)
# db_filename = "cms.db"

# app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///%s" % db_filename
# app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# app.config["SQLALCHEMY_ECHO"] = True

# db.init_app(app)
# with app.app_context():
#     db.create_all()

# # generalized response formats
# def success_response(data, code=200):
#     return json.dumps(data), code


# def failure_response(message, code=404):
#     return json.dumps({"error": message}), code

# # routes here

# @app.route("/api/schedules/<int:uid>/")
# def get_schedule(uid):
#     """
#     Endpoint for getting the schedule for a given user.
#     (Assumes users only have one schedule)
#     """
#     s = Schedule.query.filter_by(user_id=uid).first() 
#     if s is None:
#         return failure_response({"error": "schedule does not exist for given user"}, 404)
#     return success_response(s.serialize(), 200)
        
# @app.route("/api/schedules/<int:uid>/create/")
# def create_schedule(uid):
#     """
#     Endpoint for creating an empty schedule for a given user.
#     """
#     if User.query.filter_by(id=uid).first() is None:
#         return failure_response({"error": "invalid user id"}, 404)
#     s = Schedule(user_id = uid)
#     return success_response(s.serialize(), 201)

# @app.route("/api/schedules/<int:uid>/add/", methods = ["POST"])
# def add_course_to_schedule():
#     user = User.query.filter_by(id=uid).first()
#     if user is None:
#         return failure_response({"error": "invalid user id"}, 404)
#     body = json.loads(request.data)
#     # --> Stuff goes here to process input courses
#     # if body.get("offerin") is None or body.get("name") is None:
#     #     return failure_response("missing input", 400)
#     # new_course = Course(code=body.get("code"), name=body.get("name"))
#     # db.session.add(new_course)
#     # db.session.commit()
#     return success_response(new_course.serialize(), 201)

###################################3