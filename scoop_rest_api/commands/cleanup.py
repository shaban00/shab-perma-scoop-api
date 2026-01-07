"""
`commands.cleanup` module: Controller for the `cleanup` CLI command.
"""

import os
import datetime
import shutil
import time

import click
from pathlib import Path
from flask import current_app

from ..models import Capture

#
# Commands
#


@current_app.cli.command("cleanup")
def cleanup() -> None:
    """
    - Clears expired files from temporary storage .
    - Clears expired captures from the database.
    - Marks failed captures as failed.
    """
    _cleanup_local()
    _cleanup_global()


@current_app.cli.command("cleanup-local")
def cleanup_local() -> None:
    """
    Clears temporary storage of expired files.
    """
    _cleanup_local()


@current_app.cli.command("cleanup-global")
def cleanup_global() -> None:
    """
    Clears expired captures from the database and marks hung captures as failed.
    """
    _cleanup_global()


#
# Helpers
#


def _cleanup_local() -> None:
    """
    Clears temporary storage of expired files.
    """
    TEMPORARY_STORAGE_EXPIRATION = int(current_app.config["TEMPORARY_STORAGE_EXPIRATION"])

    #
    # Scoop's temporary folder, in case there are lingering files there.
    #
    SCOOP_TMP_PATH = Path("node_modules") / "@harvard-lil" / "scoop" / "tmp"

    if SCOOP_TMP_PATH.exists():
        scoop_dir_start = time.time()
        for directory in [d for d in SCOOP_TMP_PATH.iterdir() if d.is_dir()]:
            # Directory must have been created more than TEMPORARY_STORAGE_EXPIRATION seconds ago
            diff = datetime.datetime.now().timestamp() - os.stat(directory).st_mtime

            if diff >= TEMPORARY_STORAGE_EXPIRATION:
                click.echo(f"{directory} has expired and will be deleted")
                shutil.rmtree(directory)
        click.echo(f"Cleaned Scoop's tmp dir in {time.time() - scoop_dir_start}.")
    else:
        click.echo(f"No Scoop tmp dir to clean.")


def _cleanup_global() -> None:
    """
    Clears expired captures from the database and marks hung captures as failed.
    """
    TEMPORARY_STORAGE_EXPIRATION = int(current_app.config["TEMPORARY_STORAGE_EXPIRATION"])

    #
    # Mark "started" captures from > 1 hour ago as "failed"
    #
    stale_started_captures_query_start = time.time()
    queryset_evaluated = False
    stale_started_captures = Capture.select().where(
        Capture.status == "started",
        Capture.started_timestamp < datetime.datetime.utcnow() - datetime.timedelta(hours=1),
    )
    for capture in stale_started_captures:
        if not queryset_evaluated:
            queryset_evaluated = True
            click.echo(
                f"Retrieved stale started captures in {time.time() - stale_started_captures_query_start}."
            )
        click.echo(f"#{capture.id_capture} is stale and will be marked as failed.")
        capture.status = "failed"
        capture.ended_timestamp = datetime.datetime.utcnow()
        capture.save()
    else:
        queryset_evaluated = True
        click.echo(
            f"Found zero stale started captures in {time.time() - stale_started_captures_query_start}."
        )
    click.echo(
        f"Cleaned up stale started captures in {time.time() - stale_started_captures_query_start}."
    )

    #
    # Delete captures from > TEMPORARY_STORAGE_EXPIRATION from the database
    #
    delete_query_start = time.time()
    expired = Capture.delete().where(
        Capture.started_timestamp
        < datetime.datetime.utcnow() - datetime.timedelta(seconds=TEMPORARY_STORAGE_EXPIRATION),
    )
    count = expired.execute()
    click.echo(f"Deleted {count} captures from the database in {time.time() - delete_query_start}.")
