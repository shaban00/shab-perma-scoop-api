"""Obtain a Celery instance for the Celery worker to use.

This is required because we use the factory pattern to instantiate our
Flask app. See Flask documentation for details:

    https://flask.palletsprojects.com/en/2.3.x/patterns/celery/
"""

from scoop_rest_api import create_app

flask_app = create_app()
celery_app = flask_app.extensions["celery"]
