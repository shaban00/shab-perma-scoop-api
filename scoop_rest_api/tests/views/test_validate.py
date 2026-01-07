"""
Test suite for "views.validate"
"""

from requests import TooManyRedirects


def test_validate_post_get_missing_access_key(client):
    """[POST] /validate returns HTTP 401 if no Access-Key was provided."""
    response = client.post("/validate")
    assert response.status_code == 401
    assert "error" in response.get_json()


def test_validate_post_no_url(client, access_key):
    """[POST] /validate returns HTTP 400 if no URL to validate is provided."""
    # set up
    access_key_readable = access_key["readable"]

    # test
    response = client.post("/validate", headers={"Access-Key": access_key_readable}, json={})
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_validate_post_invalid_url(client, access_key):
    """[POST] /validate returns HTTP 200 + message if an invalid URL is provided."""
    # set up
    access_key_readable = access_key["readable"]

    # test
    response = client.post(
        "/validate",
        headers={"Access-Key": access_key_readable},
        json={"url": "foo-bar-baz"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert not data["valid"]
    assert data["message"] == "Not a valid URL."


def test_validate_post_unresolvable_url(client, access_key, monkeypatch):
    """[POST] /validate returns HTTP 200 + message if an unresolvable URL is provided."""
    # set up
    access_key_readable = access_key["readable"]
    monkeypatch.setattr("scoop_rest_api.views.validate.resolve_ip", lambda *args, **kwargs: None)

    # test
    response = client.post(
        "/validate",
        headers={"Access-Key": access_key_readable},
        json={"url": "http://example.com"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert not data["valid"]
    assert data["message"] == "Couldn't resolve domain."


def test_validate_post_blocked_ip(client, access_key, monkeypatch):
    """
    [POST] /validate returns HTTP 200 + message
    if a URL that resolves to a forbidden IP is provided.
    """
    # set up
    access_key_readable = access_key["readable"]
    monkeypatch.setattr(
        "scoop_rest_api.views.validate.resolve_ip", lambda *args, **kwargs: "1.1.1.1"
    )
    monkeypatch.setattr("scoop_rest_api.views.validate.validate_ip", lambda *args, **kwargs: False)

    # test
    response = client.post(
        "/validate",
        headers={"Access-Key": access_key_readable},
        json={"url": "http://example.com"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert not data["valid"]
    assert data["message"] == "Not a valid IP."


def test_validate_post_site_unresponsive(client, access_key, monkeypatch):
    """[POST] /validate returns HTTP 200 + message if the site is unresponsive."""
    # set up
    access_key_readable = access_key["readable"]
    monkeypatch.setattr(
        "scoop_rest_api.views.validate.resolve_ip", lambda *args, **kwargs: "1.1.1.1"
    )
    monkeypatch.setattr("scoop_rest_api.views.validate.get_response", lambda *args, **kwargs: None)

    # test
    response = client.post(
        "/validate",
        headers={"Access-Key": access_key_readable},
        json={"url": "http://example.com"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert not data["valid"]
    assert data["message"] == "Couldn't load URL."


def test_validate_post_redirect_loop(client, access_key, monkeypatch):
    """[POST] /validate returns HTTP 200 + message if we get stuck in a redirect loop."""

    # set up
    def redirect_loop(*args, **kwargs):
        raise TooManyRedirects()

    access_key_readable = access_key["readable"]
    monkeypatch.setattr(
        "scoop_rest_api.views.validate.resolve_ip", lambda *args, **kwargs: "1.1.1.1"
    )
    monkeypatch.setattr("scoop_rest_api.views.validate.get_response", redirect_loop)

    # test
    response = client.post(
        "/validate",
        headers={"Access-Key": access_key_readable},
        json={"url": "http://example.com"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert not data["valid"]
    assert data["message"] == "URL caused a redirect loop."


def test_validate_post_valid_url_with_content_length(
    client, access_key, monkeypatch, mock_response_factory
):
    """[POST] /validate returns HTTP 200 + content_length if valid."""
    # set up
    resp = mock_response_factory()
    access_key_readable = access_key["readable"]
    monkeypatch.setattr(
        "scoop_rest_api.views.validate.resolve_ip", lambda *args, **kwargs: "1.1.1.1"
    )
    monkeypatch.setattr("scoop_rest_api.views.validate.get_response", lambda *args, **kwargs: resp)

    # test
    response = client.post(
        "/validate",
        headers={"Access-Key": access_key_readable},
        json={"url": "http://example.com"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["valid"]
    assert data["content_length"] == int(resp.headers["Content-Length"])


def test_validate_post_valid_url_without_content_length(
    client, access_key, monkeypatch, mock_response_factory
):
    """[POST] /validate returns HTTP 200 if valid."""
    # set up
    resp = mock_response_factory()
    resp.headers.pop("Content-Length")
    access_key_readable = access_key["readable"]
    monkeypatch.setattr(
        "scoop_rest_api.views.validate.resolve_ip", lambda *args, **kwargs: "1.1.1.1"
    )
    monkeypatch.setattr("scoop_rest_api.views.validate.get_response", lambda *args, **kwargs: resp)

    # test
    response = client.post(
        "/validate",
        headers={"Access-Key": access_key_readable},
        json={"url": "http://example.com"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["valid"]
    assert "content_length" not in data


def test_validate_post_valid_but_tricky_url(client, access_key, monkeypatch, mock_response_factory):
    """[POST] /validate returns HTTP 200 if valid."""
    # set up
    resp = mock_response_factory()
    access_key_readable = access_key["readable"]
    monkeypatch.setattr(
        "scoop_rest_api.views.validate.resolve_ip", lambda *args, **kwargs: "1.1.1.1"
    )
    monkeypatch.setattr("scoop_rest_api.views.validate.get_response", lambda *args, **kwargs: resp)

    # test
    tricky_url = "https://example.com/abc#/def/?abc=def&ghi=&xyz=true"
    response = client.post(
        "/validate",
        headers={"Access-Key": access_key_readable},
        json={"url": tricky_url},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["valid"]
