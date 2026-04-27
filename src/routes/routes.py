from flask import Blueprint, jsonify, request

from db import MajorRequirement, User, db

main = Blueprint("main", __name__)


@main.get("/")
def health_check() -> str:
    return "CourseFinderBackend is running."


@main.post("/users/")
def create_user():
    payload = request.get_json(silent=True) or {}

    required_fields = ("name", "major", "year")
    missing = [field for field in required_fields if payload.get(field) in (None, "")]

    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    try:
        user = User(
            name=str(payload["name"]).strip(),
            major=str(payload["major"]).strip(),
            year=int(payload["year"]),
        )
        db.session.add(user)
        db.session.commit()
        return jsonify(
            {"id": user.id, "name": user.name, "major": user.major, "year": user.year}
        ), 201
    except Exception as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


@main.get("/users/")
def list_users():
    users = User.query.all()
    return jsonify(
        [
            {"id": user.id, "name": user.name, "major": user.major, "year": user.year}
            for user in users
        ]
    )


@main.post("/major-requirements/")
def create_major_requirement():
    payload = request.get_json(silent=True) or {}

    required_fields = ("major", "requirement_group", "requirement_type", "course_id")
    missing = [field for field in required_fields if payload.get(field) in (None, "")]

    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    try:
        req = MajorRequirement(
            major=str(payload["major"]).strip(),
            requirement_group=str(payload["requirement_group"]).strip(),
            requirement_type=str(payload["requirement_type"]).strip(),
            course_id=str(payload["course_id"]).strip(),
            group_id=(str(payload["group_id"]).strip() if payload.get("group_id") else None),
        )
        db.session.add(req)
        db.session.commit()
        return jsonify(
            {
                "id": req.id,
                "major": req.major,
                "requirement_group": req.requirement_group,
                "requirement_type": req.requirement_type,
                "course_id": req.course_id,
                "group_id": req.group_id,
            }
        ), 201
    except Exception as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


@main.get("/major-requirements/")
def list_major_requirements():
    major = request.args.get("major")

    query = MajorRequirement.query
    if major:
        query = query.filter(MajorRequirement.major == major)

    rows = query.all()

    return jsonify(
        [
            {
                "id": row.id,
                "major": row.major,
                "requirement_group": row.requirement_group,
                "requirement_type": row.requirement_type,
                "course_id": row.course_id,
                "group_id": row.group_id,
            }
            for row in rows
        ]
    )
