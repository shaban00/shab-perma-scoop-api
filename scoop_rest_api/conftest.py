""" Test suite configuration and fixtures. """

import os
from requests.models import Response
from tempfile import TemporaryDirectory
from urllib3.response import HTTPResponse
import uuid

import pytest
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

from scoop_rest_api import create_app

load_dotenv()


@pytest.fixture(scope="session")
def app():
    """
    Creates a test-specific app context as well as a dedicated database for this test suite.

    Default test credentials can be replaced using environment variables:
    - TESTS_DATABASE_HOST
    - TESTS_DATABASE_USERNAME
    - TESTS_DATABASE_PASSWORD
    - TESTS_DATABASE_PORT
    """
    with TemporaryDirectory() as temporary_dir:
        DATABASE_HOST = "127.0.0.1"
        DATABASE_USERNAME = "scoop"
        DATABASE_PASSWORD = "password"
        DATABASE_PORT = 5432
        DATABASE_NAME = str(uuid.uuid4())

        # Default test credentials can be replaced using environment variables.
        if "TESTS_DATABASE_HOST" in os.environ:
            DATABASE_HOST = os.environ["TESTS_DATABASE_HOST"]

        if "TESTS_DATABASE_USERNAME" in os.environ:
            DATABASE_USERNAME = os.environ["TESTS_DATABASE_USERNAME"]

        if "TESTS_DATABASE_PASSWORD" in os.environ:
            DATABASE_PASSWORD = os.environ["TESTS_DATABASE_PASSWORD"]

        if "TESTS_DATABASE_PORT" in os.environ:
            DATABASE_PORT = int(os.environ["TESTS_DATABASE_PORT"])

        # Create temporary database
        db = psycopg2.connect(
            host=DATABASE_HOST,
            user=DATABASE_USERNAME,
            password=DATABASE_PASSWORD,
            port=DATABASE_PORT,
            dbname="postgres",
        )

        db.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        cur = db.cursor()

        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DATABASE_NAME)))

        # Create app context
        app = create_app(
            {
                "DATABASE_USERNAME": DATABASE_USERNAME,
                "DATABASE_PASSWORD": DATABASE_PASSWORD,
                "DATABASE_HOST": DATABASE_HOST,
                "DATABASE_PORT": DATABASE_PORT,
                "DATABASE_NAME": DATABASE_NAME,
                "DATABASE_CA_PATH": "",
                "MAX_PENDING_CAPTURES": 5,
                "MAX_SUPPORTED_ARCHIVE_FILESIZE": 1e6 / 2,  # 1/2 MB
                "EXPOSE_SCOOP_LOGS": True,
                "EXPOSE_SCOOP_CAPTURE_SUMMARY": True,
                "TEMPORARY_STORAGE_EXPIRATION": 3,
                "ENABLE_CELERY_BACKEND": True,
            }
        )

        # Create tables
        with app.app_context():
            from scoop_rest_api.utils import get_db
            from scoop_rest_api.models import AccessKey, Capture

            get_db().create_tables([AccessKey, Capture])

        # Run tests
        yield app

        # Drop database once test session is complete
        #
        # Note: This won't run if the test suite crashes.
        # This gives us the opportunity to inspect the database that was used during the crash.
        # This is TBD -- we can also cleanup on crash.

        cur.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(DATABASE_NAME)))
        db.close()


@pytest.fixture(autouse=True)
def database_cleanup(app):
    """
    Clear leftover records before each test.
    """
    with app.app_context():
        from scoop_rest_api.models import AccessKey, Capture

        Capture.delete().execute()
        AccessKey.delete().execute()

        yield


@pytest.fixture()
def access_key(app) -> dict:
    """
    Creates, stores and return an access key for the current test.
    Returned dict contains an AccessKey object and the human-readable access key.
    """
    with app.app_context():
        from scoop_rest_api.models import AccessKey

        access_key_digest = AccessKey.create_key_digest(salt=app.config["ACCESS_KEY_SALT"])
        access_key = AccessKey.create(label="Test", key_digest=access_key_digest[1])
        access_key_readable = access_key_digest[0]

    return {"instance": access_key, "readable": access_key_readable}


@pytest.fixture()
def client(app):
    """Returns a Flask HTTP test client for the current app."""
    return app.test_client()


@pytest.fixture()
def runner(app):
    """Returns a Flask CLI test client for the current app."""
    return app.test_cli_runner()


@pytest.fixture(scope="session")
def celery_app(app):
    """
    Tells Celery to use our Flask app's celery app during testing,
    instead of spinning up a fresh, vanilla Celery app
    """
    return app.extensions["celery"]


@pytest.fixture
def celery_worker_parameters():
    return {
        # Our celery app doesn't have the "ping" task that is part
        # of the vanilla Celery testing app, so disable the ping check
        "perform_ping_check": False,
        # Configure the test worker to listen for tasks sent to
        # our "main" queue
        "queues": ["main", "background"],
    }


@pytest.fixture()
def default_capture_url() -> str:
    return "https://example.com"


@pytest.fixture()
def large_capture_url() -> str:
    return "https://lil.law.harvard.edu/"


@pytest.fixture()
def default_artifact_filename() -> str:
    return "archive.wacz"


@pytest.fixture()
def id_capture(app, client, access_key, default_capture_url) -> str:
    """
    Creates a capture request for the default capture URL.
    This means that every test will have a pending capture in the queue.
    Returns id_capture.
    """
    with app.app_context():
        from scoop_rest_api.models import Capture

        capture = client.post(
            "/capture",
            headers={"Access-Key": access_key["readable"]},
            json={"url": default_capture_url},
        )

        return capture.get_json()["id_capture"]


@pytest.fixture()
def id_capture_large(app, client, access_key, large_capture_url) -> str:
    """
    Creates a capture request for the default capture URL.
    This means that every test will have a pending capture in the queue.
    Returns id_capture.
    """
    with app.app_context():
        from scoop_rest_api.models import Capture

        capture = client.post(
            "/capture",
            headers={"Access-Key": access_key["readable"]},
            json={"url": large_capture_url},
        )

        return capture.get_json()["id_capture"]


@pytest.fixture()
def mock_response_factory():
    """
    Create functioning python requests.Response objects
    """

    def f(status_code=200, override_headers=None):
        resp = Response()
        resp.status_code = status_code
        resp._content = b'{ "key" : "a" }'
        resp.raw = HTTPResponse()

        # Headers returned by one GET request to http://example.com
        resp.headers = {
            "Content-Encoding": "gzip",
            "Accept-Ranges": "bytes",
            "Age": "455555",
            "Cache-Control": "max-age=604800",
            "Content-Type": "text/html; charset=UTF-8",
            "Date": "Wed, 20 Dec 2023 14:58:41 GMT",
            "Etag": '"3147526947+gzip"',
            "Expires": "Wed, 27 Dec 2023 14:58:41 GMT",
            "Last-Modified": "Thu, 17 Oct 2019 07:18:26 GMT",
            "Server": "ECS (bsb/27E0)",
            "Vary": "Accept-Encoding",
            "X-Cache": "HIT",
            "Content-Length": "648",
        }
        if override_headers:
            for header in override_headers:
                resp.headers[header] = override_headers[header]
        return resp

    return f
