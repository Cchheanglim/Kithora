import os
import tempfile

# Must run before the app is imported: isolated DB, no real speech engine.
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ["GEMINI_API_KEY"] = ""
os.environ["KETHRA_DEFAULT_ENGINE"] = "mock-deterministic"

import pytest
from fastapi.testclient import TestClient

from app import security
from app.main import app


@pytest.fixture(autouse=True)
def reset_limits():
    security._requests.clear()
    security._open_streams.clear()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


_counter = iter(range(10**6))


@pytest.fixture
def user(client):
    """Registers a fresh account; the client keeps its login cookie."""
    email, password = f"user{next(_counter)}@example.com", "correct horse battery"
    assert client.post("/v1/auth/register", json={"email": email, "password": password}).status_code == 201
    return {"email": email, "password": password}

