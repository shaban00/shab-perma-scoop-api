"""
`utils.capture_to_dict` module: Converts a Capture object to dictionary.
"""

from flask import current_app


def capture_to_dict(capture) -> dict:
    """
    Formats a models.Capture object into a dictionary.
    Only lists properties the end-user should be able to see.
    """
    from ..models import Capture

    if not isinstance(capture, Capture):
        raise Exception("capture must be a valid Capture object")

    to_return = {
        "id_capture": capture.id_capture,
        "status": capture.status,
        "created_timestamp": capture.created_timestamp,
        "started_timestamp": capture.started_timestamp,
        "ended_timestamp": capture.ended_timestamp,
        "url": capture.url,
        "callback_url": capture.callback_url,
    }

    api_domain = current_app.config["API_DOMAIN"]

    #
    # Properties specific to status "pending" or "started"
    #
    if capture.status == "pending" or capture.status == "started":
        to_return["follow"] = f"{api_domain}/capture/{capture.id_capture}"

    #
    # Properties specific to status "success"
    #
    if capture.status == "success":
        # Generate "/artifact" URLs for all existing files, except "archive.json"
        to_return["artifacts"] = [
            f"{api_domain}/artifact/{capture.id_capture}/{filename}"
            for filename in ["archive.wacz"] + list(capture.summary["attachments"].values())
        ]

        if to_return["artifacts"]:
            to_return["temporary_playback_url"] = (
                f"https://replayweb.page/?source={to_return['artifacts'][0]}"
            )

    #
    # Expose logs?
    #
    if capture.status in ["success", "failed"] and current_app.config["EXPOSE_SCOOP_LOGS"]:
        to_return["stdout_logs"] = capture.stdout_logs
        to_return["stderr_logs"] = capture.stderr_logs

    #
    # Expose capture summary?
    #
    if (
        capture.status in ["success", "failed"]
        and current_app.config["EXPOSE_SCOOP_CAPTURE_SUMMARY"]
    ):
        to_return["scoop_capture_summary"] = capture.summary

    return to_return
