"""
Test suite for "utils.validation_helpers"
"""

from requests import ConnectionError
import logging


def test_should_reject_unresolvable_ip():
    from scoop_rest_api.utils import resolve_ip

    assert resolve_ip("http://this-is-not-a-functioning-url.com") is None


def test_should_accept_resolvable_ip():
    from scoop_rest_api.utils import resolve_ip

    assert resolve_ip("http://1.1.1.1")


def test_should_reject_blocked_ip(app):
    with app.app_context():
        from scoop_rest_api.utils import validate_ip

        assert not validate_ip("198.51.100.1")


def test_should_reject_blocked_ip_2(app):
    with app.app_context():
        from scoop_rest_api.utils import validate_ip

        assert not validate_ip("127.0.0.1")


def test_should_accept_standard_ip(app):
    with app.app_context():
        from scoop_rest_api.utils import validate_ip

        assert validate_ip("1.1.1.1")


def test_should_return_headers_from_live_site(app, monkeypatch, mock_response_factory):
    response = mock_response_factory()
    monkeypatch.setattr("requests.adapters.HTTPAdapter.send", lambda *args, **kwargs: response)

    with app.app_context():
        from scoop_rest_api.utils import get_response

        resp = get_response("http://this-is-not-a-functioning-url.com")
        assert response.headers == resp.headers


def test_should_return_no_headers_if_site_is_down(app, monkeypatch):
    def site_is_down(*args, **kwargs):
        raise ConnectionError()

    monkeypatch.setattr("requests.adapters.HTTPAdapter.send", site_is_down)

    with app.app_context():
        from scoop_rest_api.utils import get_response

        response = get_response("http://this-is-not-a-functioning-url.com")
        assert response is None


def test_should_return_no_headers_if_site_times_out(
    app, monkeypatch, caplog, mock_response_factory
):
    def site_times_out(*args, **kwargs):
        from time import sleep

        sleep(1)

        return mock_response_factory()

    from flask import current_app

    monkeypatch.setitem(current_app.config, "VALIDATION_TIMEOUT", 0.1)
    monkeypatch.setattr("requests.adapters.HTTPAdapter.send", site_times_out)

    with caplog.at_level(logging.INFO):

        with app.app_context():
            from scoop_rest_api.utils import get_response

            response = get_response("http://example.com")
            assert response is None

        [log] = caplog.records
        assert "Header retrieval timed out" in log.message


def test_should_return_content_length_if_present(app, mock_response_factory):
    response = mock_response_factory()

    with app.app_context():
        from scoop_rest_api.utils import get_content_length

        assert get_content_length(response.headers) == int(response.headers["Content-Length"])


def test_should_return_no_content_length_if_malformed(app, mock_response_factory):
    response = mock_response_factory(override_headers={"Content-Length": "foo"})

    with app.app_context():
        from scoop_rest_api.utils import get_content_length

        assert get_content_length(response.headers) is None


def test_should_return_no_content_length_if_absent(app, mock_response_factory):
    response = mock_response_factory()
    response.headers.pop("Content-Length")

    with app.app_context():
        from scoop_rest_api.utils import get_content_length

        assert get_content_length(response.headers) is None
