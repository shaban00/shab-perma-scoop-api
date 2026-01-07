"""
`views.validate` module: URL validation route.
"""

from flask import request, jsonify, current_app
import requests
import validators

from ..utils import access_check, resolve_ip, validate_ip, get_response, get_content_length


@current_app.route("/validate", methods=["POST"])
@access_check
def validate_post():
    """
    [POST] /validate
    Checks to see if a URL is a valid capture target.

    Behind auth: Requires Access-Key header (see utils.access_check).

    Accepts JSON body with the following properties:
    - "url": Url to validate (required)

    Returns HTTP 200 and a JSON object containing user-facing capture information.
    """
    input = request.get_json()
    url = None

    #
    # Required input: url
    #
    if "url" not in input:
        return jsonify({"error": "No URL provided."}), 400

    url = input["url"]

    #
    # Validate URL
    #
    # Does the URL appear to be valid?
    strict = current_app.config["STRICT_URL_VALIDATION"]
    if validators.url(url, strict_query=strict) is not True:
        return jsonify({"valid": False, "message": "Not a valid URL."}), 200

    # Does the domain name resolve?
    try:
        if not (ip := resolve_ip(url)):
            return jsonify({"valid": False, "message": "Couldn't resolve domain."}), 200
    except OSError:
        return jsonify({"valid": False, "message": "Couldn't resolve domain promptly."}), 200

    # Does the domain resolve to an allowed IP range?
    if not validate_ip(ip):
        return jsonify({"valid": False, "message": "Not a valid IP."}), 200

    # Does the page respond to our requests?
    try:
        response = get_response(url)
    except requests.TooManyRedirects:
        return jsonify({"valid": False, "message": "URL caused a redirect loop."}), 200
    # With requests < 3, responses where response.ok() is false are falsey.
    # So, explicitly check for None
    if response is None:
        return jsonify({"valid": False, "message": "Couldn't load URL."}), 200

    # The URL is valid! Return the content length if we have one
    if content_length := get_content_length(response.headers):
        return (
            jsonify(
                {
                    "valid": True,
                    "status_code": response.status_code,
                    "content_length": content_length,
                }
            ),
            200,
        )
    return (
        jsonify(
            {
                "valid": True,
                "status_code": response.status_code,
            }
        ),
        200,
    )
