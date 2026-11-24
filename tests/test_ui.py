from fastapi.testclient import TestClient


def test_app_endpoint_serves_html(client: TestClient) -> None:
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "text/html" in res_root.headers["content-type"]
    assert "StoreStock" in res_root.text

    res = client.get("/app")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "StoreStock" in res.text
    assert 'id="login-view"' in res.text

    res_slash = client.get("/app/")
    assert res_slash.status_code == 200
    assert "text/html" in res_slash.headers["content-type"]


def test_static_files_served(client: TestClient) -> None:
    css_res = client.get("/static/style.css")
    assert css_res.status_code == 200
    assert "text/css" in css_res.headers["content-type"]
    assert "--primary" in css_res.text

    js_res = client.get("/static/app.js")
    assert js_res.status_code == 200
    assert "javascript" in js_res.headers["content-type"]
    assert "authToken" in js_res.text
