"""
`scoop_rest_api` module: REST API for the `scoop-rest-api` project.
"""

import logging
from pathlib import Path

from celery import Celery, Task
from flask import Flask

from scoop_rest_api import utils


def create_app(config_override: dict = {}):
    """
    App factory (https://flask.palletsprojects.com/en/2.3.x/patterns/appfactories/)
    config_override allows to replace app config values on an in-instance basis.
    """
    app = Flask(__name__)
    app.config.from_object("scoop_rest_api.config")

    # Handle config override
    if config_override and isinstance(config_override, dict):
        for key, value in config_override.items():
            if key in app.config:
                app.config[key] = value

    # Configure app logger
    app.logger.setLevel(logging.INFO)

    # Note: Every module in this app assumes the app context is available and initialized.
    with app.app_context():
        # Check that provided configuration is sufficient to run the app
        utils.config_check()

        # Import views
        from scoop_rest_api import commands, views

        # Initialize Celery
        create_celery_app(app)

        return app


def create_celery_app(app: Flask) -> Celery:
    """
    Create and configure a Celery instance on the Flask app.

    Adapted from https://flask.palletsprojects.com/en/2.3.x/patterns/celery.
    """

    class FlaskTask(Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(app.name, task_cls=FlaskTask)

    # only schedule those celerybeat tasks that are listed in CELERYBEAT_TASKS
    celerybeat_schedule = {}
    for task_name, task_config in app.config["CELERY_SETTINGS"]["beat_schedule"].items():
        if task_name in app.config["CELERYBEAT_TASKS"]:
            celerybeat_schedule[task_name] = task_config
    app.config["CELERY_SETTINGS"]["beat_schedule"] = celerybeat_schedule

    if not app.config["ENABLE_CELERY_BACKEND"]:
        app.config["CELERY_SETTINGS"].pop("result_backend", None)

    celery_app.config_from_object(app.config["CELERY_SETTINGS"])
    celery_app.set_default()
    app.extensions["celery"] = celery_app
    return celery_app
