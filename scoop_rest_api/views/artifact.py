"""
`views.artifact` module: Provides regulated access to capture artifacts.
"""

from pathlib import Path
import re
import uuid
import io
from zipfile import ZipFile

from flask import jsonify, make_response, send_file, current_app

from scoop_rest_api.models import Capture


@current_app.route("/artifact/<string:id_capture>/<string:filename>")
def artifact_get(id_capture, filename):
    """
    [GET] /artifact/<id_capture>/<filename>
    Retrieves a specific artifact from a given capture.
    `id_capture` and `filename` params must be provided.

    Not behind auth.
    """

    # Is id_capture an uuid?
    try:
        uuid.UUID(id_capture, version=4)  # noqa
    except ValueError:
        return jsonify({"error": "Invalid format for id_capture."}), 400

    # `filename` must be one of:
    # - "archive.wacz"
    # - "data.warc.gz" or "archive.warc.gz" (will be extracted from the WACZ via /archive/)
    # - "*.(pem|png|pdf|html|mp4|vtt)" (will be loaded from /attachments/)
    attachments_pattern = r"^[\w._-]+\.(pem|png|pdf|html|mp4|vtt)$"

    # Retrieve the WACZ or an associated file (WARC or attachment) from the database
    match filename:
        # WACZ
        case "archive.wacz":
            data = retrieve_artifact(id_capture, filename)
        # WARC
        case "data.warc.gz" | "archive.warc.gz":
            wacz = retrieve_artifact(id_capture, "archive.wacz")
            if not wacz:
                return jsonify({"error": "Requested file was not found."}), 404
            with ZipFile(io.BytesIO(wacz)) as zip_file:
                data = zip_file.open("archive/data.warc.gz").read()
        # Attachment
        case _ if re.match(attachments_pattern, filename):
            data = retrieve_artifact(id_capture, filename, attachment=True)
        # If any other filename was requested, return an error
        case _:
            return jsonify({"error": "Invalid filename provided."}), 400

    if not data:
        return jsonify({"error": "Requested file was not found."}), 404

    # Return file
    response = make_response(
        send_file(io.BytesIO(data), as_attachment=True, download_name=filename),
    )
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"

    response.headers["Access-Control-Expose-Headers"] = (
        "Content-Range, Content-Encoding, Content-Length"
    )

    return response


def retrieve_artifact(id_capture, filename, attachment=False):
    """Gets a capture file from the database."""
    try:
        capture = Capture.get_by_id(id_capture)
        if capture.status == "pending":
            return None
    except Capture.DoesNotExist:
        return None

    if attachment:
        with ZipFile(io.BytesIO(capture.attachments)) as container:
            for zip_info in container.infolist():
                if zip_info.filename == filename:
                    with container.open(zip_info) as contents:
                        data = contents.read()
    else:
        data = capture.archive

    return data
