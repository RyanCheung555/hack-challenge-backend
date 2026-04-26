from flask import Flask

from src.routes.routes import main


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(main)
    return app
