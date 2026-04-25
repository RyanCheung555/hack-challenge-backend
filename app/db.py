from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class BaseModel(db.Model):
    """Shared base model with common helpers."""

    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True)

    def to_dict(self) -> dict:
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}
