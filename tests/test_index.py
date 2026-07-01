import importlib
import pytest


@pytest.fixture
def client(temp_db):
    import app as app_module
    importlib.reload(app_module)
    return app_module.app.test_client()


def test_index_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "SPOTTER" in body          # rebranded wordmark present
    assert "cat-toggle" in body       # category filter strip present
    assert "ticker" in body           # news ticker present
