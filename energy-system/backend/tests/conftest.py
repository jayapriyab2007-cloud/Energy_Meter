import os
import sys
import tempfile
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set test environment
os.environ["ENV"] = "development"
os.environ["JWT_SECRET"] = "test-secret-key-1234567890"

from app.models import Base
from app.database import get_db
from app.main import app
from app.seed_demo import seed_demo

@pytest.fixture(scope="session")
def test_db_engine():
    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_file.close()
    url = f"sqlite:///{db_file.name}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Seed demo data
    db = TestingSessionLocal()
    seed_demo(db)
    db.close()
    
    yield engine, TestingSessionLocal
    
    try:
        os.remove(db_file.name)
    except Exception:
        pass

@pytest.fixture
def db_session(test_db_engine):
    engine, TestingSessionLocal = test_db_engine
    session = TestingSessionLocal()
    yield session
    session.close()

@pytest.fixture
def client(test_db_engine):
    engine, TestingSessionLocal = test_db_engine
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
            
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture
def admin_token(client):
    res = client.post("/api/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200, res.text
    return res.json()["token"]

@pytest.fixture
def consumer_token(client):
    res = client.post("/api/login", json={"username": "consumer", "password": "consumer123"})
    assert res.status_code == 200, res.text
    return res.json()["token"]
