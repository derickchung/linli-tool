import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.main import app
from backend.models import User, VerificationStatus
from backend.services.auth_service import AuthService, otp_store

# In-Memory SQLite for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_database():
    """Create fresh tables for every test."""
    Base.metadata.create_all(bind=engine)
    # Clear in-memory OTP store before each test
    otp_store._otps.clear()
    otp_store._request_history.clear()
    from backend.ai.gateway import AIGateway
    AIGateway.get_instance().rate_limits.clear()
    AIGateway.get_instance().prompt_cache.clear()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def create_test_user(db_session):
    def _create_user(phone="0911222333", name="測試住戶", status=VerificationStatus.PENDING, community_id=None):
        user = User(
            phone=phone,
            name=name,
            verification_status=status,
            community_id=community_id,
            credit_score=80,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        token = AuthService.create_access_token(user.id, user.community_id)
        return user, token
    return _create_user
