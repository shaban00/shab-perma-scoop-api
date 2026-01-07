"""
`utils.get_db` module: Returns a connection to the database.
"""

from pathlib import Path

from peewee import PostgresqlDatabase
from flask import current_app


def get_db() -> PostgresqlDatabase:
    """
    Returns a database object.
    """
    with current_app.app_context():
        ssl = {}
        ca_path = current_app.config["DATABASE_CA_PATH"]

        # Use SSL cert if provided
        if ca_path and Path(ca_path).exists():
            ssl = {"sslmode": "verify-ca", "sslrootcert": ca_path}
        return PostgresqlDatabase(
            current_app.config["DATABASE_NAME"],
            user=current_app.config["DATABASE_USERNAME"],
            password=current_app.config["DATABASE_PASSWORD"],
            host=current_app.config["DATABASE_HOST"],
            port=int(current_app.config["DATABASE_PORT"]),
            autoconnect=True,
            **ssl
        )
