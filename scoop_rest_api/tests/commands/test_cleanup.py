"""
Test suite for the "cleanup" command.
"""

import time
from pathlib import Path

from flask import current_app


def test_cleanup_cli(app, runner, access_key, id_capture):
    """cleanup command deletes obsolete files and returns exit code 0."""
    from scoop_rest_api.tasks import start_capture_process

    before_cleanup = 0
    after_cleanup = 0

    def count_dirs():
        """Counts total of dirs present in Scoop's "tmp" folder."""
        paths = [
            Path("node_modules") / "@harvard-lil" / "scoop" / "tmp",
        ]
        return sum([len(list(path.iterdir())) for path in paths])

    def count_rows():
        """Counts captures in the database."""
        with app.app_context():
            from scoop_rest_api.models import Capture

            return Capture.select().count()

    # Process pending capture
    start_capture_process.run()

    # Count number of dirs in storage
    before_cleanup = count_dirs()

    # Count captures
    before_db_cleanup = count_rows()

    # Wait until expiration time is reached
    time.sleep(current_app.config["TEMPORARY_STORAGE_EXPIRATION"])

    result = runner.invoke(args="cleanup")
    after_cleanup = count_dirs()
    after_db_cleanup = count_rows()

    assert before_db_cleanup != after_db_cleanup
    assert after_cleanup == 0
    assert after_db_cleanup == 0
    assert result.exit_code == 0
