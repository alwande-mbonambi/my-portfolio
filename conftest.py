import pytest
import sys
import os
from threading import Thread
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app as flask_app
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server

# -------------------- UNIT TEST FIXTURES (with mocks) --------------------
flask_app.config['TESTING'] = True
flask_app.config['SECRET_KEY'] = 'test-secret-key'

@pytest.fixture(autouse=True)
def mock_firestore():
    with patch('app.db') as mock_db:
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "name": "Alwande Mbonambi",
            "job": "Cloud Engineer",
            "desc": "Test description",
            "pImg": "https://mock.cloudinary.com/image.jpg",
            "pZoom": 1,
            "pX": 0,
            "pY": 0,
            "cvUrl": "",
            "contactInfo": {"email": "test@example.com", "phone": "+123456789"},
            "quals": [],
            "skillCats": [],
            "projects": [],
            "certificates": [],
            "exps": [],
            "contacts": [],
            "extraKnowledge": "Test extra knowledge"
        }
        mock_collection = MagicMock()
        mock_collection.document.return_value.get.return_value = mock_doc
        mock_collection.document.return_value.set.return_value = None
        mock_db.collection.return_value = mock_collection
        yield

@pytest.fixture(autouse=True)
def mock_cloudinary():
    with patch('cloudinary.uploader.upload') as mock_upload:
        mock_upload.return_value = {"secure_url": "https://mock.cloudinary.com/uploaded.jpg"}
        yield

@pytest.fixture(autouse=True)
def mock_gemini():
    with patch('app.genai.GenerativeModel') as mock_model_class:
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "I am 22 years old, or better said young 😂"
        mock_instance.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_instance
        yield

@pytest.fixture
def app():
    return flask_app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def admin_client(client):
    with patch('app.ADMIN_PASSWORD_HASH', generate_password_hash('Alwande.m18')):
        response = client.post('/api/login', json={'password': 'Alwande.m18'})
        assert response.status_code == 200
        return client

@pytest.fixture
def sample_portfolio_data():
    return {
        "name": "Updated Name",
        "job": "Updated Job",
        "desc": "Updated description",
        "pImg": "",
        "pZoom": 1,
        "pX": 0,
        "pY": 0,
        "cvUrl": "https://mock.cv.pdf",
        "contactInfo": {"email": "new@example.com", "phone": "987654321"},
        "quals": [],
        "skillCats": [],
        "projects": [],
        "certificates": [],
        "exps": [],
        "contacts": [],
        "extraKnowledge": ""
    }

# -------------------- E2E TEST FIXTURE (Playwright) --------------------
@pytest.fixture(scope="session")
def live_server():
    """Run the Flask app on a free port for Playwright tests."""
    import socket
    sock = socket.socket()
    sock.bind(('', 0))
    port = sock.getsockname()[1]
    sock.close()
    
    server = make_server('127.0.0.1', port, flask_app)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()