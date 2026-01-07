"""
`utils.scoop_runner` module: Class for executing Scoop via a subprocess.
"""

import datetime
from io import BytesIO
import json
from pathlib import Path
import shlex
import shutil
import subprocess
from subprocess import CompletedProcess
from tempfile import mkdtemp
from typing import Any
from urllib.parse import urlparse
from zipfile import ZIP_DEFLATED, ZipFile

from flask import current_app


class ScoopRunner:
    """Class for executing Scoop via a subprocess."""

    def __init__(self, capture, proxy_port: int):
        self.capture = capture
        self.proxy_port = proxy_port
        self.capture_path = Path(mkdtemp())

    @property
    def json_summary_path(self) -> Path:
        return self.capture_path / "archive.json"

    @property
    def attachments_path(self) -> Path:
        return self.capture_path / "attachments"

    @property
    def archive_path(self) -> Path:
        return self.capture_path / "archive.wacz"

    def build_scoop_args(self) -> list[str]:
        """Build a list of Scoop args based on the current app config.

        Also creates any directories necessary for temporary storage as
        part of this Scoop run.
        """
        # Create capture-specific directories
        current_app.logger.info(
            f"Capture #{self.capture.id_capture} | Temporary storage folder: {self.capture_path}"
        )
        self.attachments_path.mkdir()

        #
        # Prepare Scoop command and options
        #
        domain = urlparse(self.capture.url).hostname

        scoop_prefix = shlex.split(current_app.config["SCOOP_PREFIX"])
        scoop_args = [
            *scoop_prefix,
            "npx",
            "scoop",
            self.capture.url,
            "--output",
            str(self.archive_path),
            "--format",
            "wacz",
            "--json-summary-output",
            str(self.json_summary_path),
            "--export-attachments-output",
            str(self.attachments_path),
            "--proxy-port",
            str(self.proxy_port),
        ]
        scoop_options: dict[str, Any] = current_app.config["SCOOP_CLI_OPTIONS"]
        for key, value in scoop_options.items():
            # Special handling for --capture-video-as-attachment:
            # Only attempt to capture videos as attachments if the target domain
            # is in the allow list.
            if (
                key == "--capture-video-as-attachment"
                and current_app.config["VIDEO_ATTACHMENT_DOMAINS"]
            ):
                if domain not in current_app.config["VIDEO_ATTACHMENT_DOMAINS"]:
                    value = "false"

            scoop_args.append(key)
            scoop_args.append(str(value))

        # Special handing for --user-agent-suffix
        from scoop_rest_api.utils.get_custom_agents import get_custom_agents  # noqa

        if custom_agents := get_custom_agents(domain):
            custom_ua_suffix = custom_agents.get("scoop_ua_suffix")
            if custom_ua_suffix:
                scoop_args.append("--user-agent-suffix")
                scoop_args.append(f" {custom_ua_suffix}")

        return scoop_args

    def save_result(self, result: CompletedProcess[bytes]):
        """Validate a Scoop result and save it to the database."""
        # Write log output to database
        self.capture.stdout_logs = result.stdout.decode("utf-8")
        self.capture.stderr_logs = result.stderr.decode("utf-8")

        # Assume capture failed until proven otherwise
        self.capture.status = "failed"
        self.capture.ended_timestamp = datetime.datetime.now(datetime.UTC)
        success = False
        failed_reason = ""

        if result.returncode != 0:
            failed_reason = f"exit code {result.returncode}"
        else:
            success = True

            # Archive file must exist
            if not self.archive_path.exists():
                failed_reason = f"{self.archive_path} not found"
                success = False
            else:
                with open(self.archive_path, "rb") as archive_file:
                    self.capture.archive = archive_file.read()

            # Archive must not be larger than max supported limit
            if len(self.capture.archive) >= current_app.config["MAX_SUPPORTED_ARCHIVE_FILESIZE"]:
                self.capture.archive = None
                failed_reason = "Archive over maximum supported filesize"
                success = False

            # JSON summary must exist
            if not self.json_summary_path.exists() and not failed_reason:
                failed_reason = f"{self.json_summary_path} not found"
                success = False

            # Analyze JSON summary and:
            # - Check that expected extracted attachments are indeed on disk
            # - Store a copy of the summary in the database
            if success is True:
                json_summary = json.loads(self.json_summary_path.read_text())
                self.capture.summary = json_summary  # Store copy of JSON summary

                filenames_to_check = []
                for filename in json_summary["attachments"].values():
                    if isinstance(filename, list):  # Example: "certificates" is a list
                        filenames_to_check.extend(filename)
                    else:
                        filenames_to_check.append(filename)

                missing_attachments = []
                attachments_buffer = BytesIO()
                with ZipFile(attachments_buffer, mode="w", compression=ZIP_DEFLATED) as zip_file:
                    for filename in filenames_to_check:
                        filepath = self.attachments_path / filename
                        if not filepath.exists():
                            missing_attachments.append(filepath)
                            current_app.logger.error(
                                f"Capture #{self.capture.id_capture} | Failed ({filepath} not found)"
                            )
                            success = False
                        else:
                            with open(filepath, "rb") as data:
                                zip_file.writestr(filename, data.read())

                # Write attachments, if any, to the database
                if filenames_to_check and len(missing_attachments) < len(filenames_to_check):
                    self.capture.attachments = attachments_buffer.getvalue()

        # Report on status and update database record
        if success is True:
            current_app.logger.info(f"Capture #{self.capture.id_capture} | Success")
            self.capture.status = "success"
        else:
            current_app.logger.error(
                f"Capture #{self.capture.id_capture} | Failed ({failed_reason})"
            )
            self.capture.status = "failed"
        self.capture.save()

    def run(self) -> None:
        """Execute Scoop for this capture."""
        # Build Scoop args and options based on the current app config
        scoop_args = self.build_scoop_args()
        capture_timeout = float(current_app.config["SCOOP_CLI_OPTIONS"]["--capture-timeout"]) / 1000

        # Run Scoop and save result
        try:
            result = subprocess.run(
                scoop_args,
                capture_output=True,
                # Enforce hard timeout after SCOOP_TIMEOUT_FUSE seconds past capture timeout
                timeout=capture_timeout + current_app.config["SCOOP_TIMEOUT_FUSE"],
            )
        except subprocess.TimeoutExpired:
            self.capture.status = "failed"
            self.capture.ended_timestamp = datetime.datetime.now(datetime.UTC)
            self.capture.save()
            current_app.logger.error(
                f"Capture #{self.capture.id_capture} | Failed (timeout violation)"
            )
        else:
            self.save_result(result)
        finally:
            shutil.rmtree(self.capture_path, ignore_errors=True)
