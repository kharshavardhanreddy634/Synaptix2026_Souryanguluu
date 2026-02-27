# tests/test_matching.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app, get_db
from database import Base
from models import Candidate, Project, Skill, Gender, SocioeconomicStatus, ProjectType
from uuid import uuid4

# Test database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(scope="function")
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    # Create test skill
    skill = Skill(id=uuid4(), name="Python", category="technical")
    db.add(skill)
    
    # Create test candidate
    candidate = Candidate(
        id=uuid4(),
        email="test@example.com",
        full_name="Test User",
        gender=Gender.FEMALE,
        socioeconomic_status=SocioeconomicStatus.LOW,
        years_experience=2
    )
    db.add(candidate)
    db.commit()
    
    yield db
    
    Base.metadata.drop_all(bind=engine)

def test_create_candidate():
    response = client.post("/candidates", json={
        "email": "new@example.com",
        "full_name": "New User",
        "password": "password123",
        "years_experience": 3,
        "demographics": {
            "gender": "female",
            "socioeconomic_status": "low"
        },
        "skills": []
    })
    assert response.status_code == 200
    assert response.json()["full_name"] == "New User"

def test_fairness_adjustment(setup_db):
    db = setup_db
    from matching_engine import ExplainableMatchingEngine
    
    engine = ExplainableMatchingEngine(db)
    candidate = db.query(Candidate).first()
    
    # Create minimal project
    from models import Project, Company
    company = Company(id=uuid4(), name="Test Co")
    db.add(company)
    db.commit()
    
    project = Project(
        id=uuid4(),
        title="Test Project",
        company_id=company.id,
        type=ProjectType.INTERNSHIP,
        weights_config={"technical": 0.6, "communication": 0.2, "leadership": 0.1, "experience": 0.1},
        fairness_config={"socioeconomic_boost": True, "gender_parity": True}
    )
    db.add(project)
    db.commit()
    
    result = engine.calculate_match(candidate, project)
    
    # Should have fairness bonus for low SES and female
    assert result["fairness_adjustment"] > 0
    assert len(result["bias_mitigation_applied"]) > 0
    assert "Socioeconomic" in result["bias_mitigation_applied"][0]

def test_explanation_generation(setup_db):
    db = setup_db
    from matching_engine import ExplainableMatchingEngine
    
    engine = ExplainableMatchingEngine(db)
    candidate = db.query(Candidate).first()
    
    # Test explanation structure
    explanations = engine._generate_explanations(
        candidate, 75.0, 80.0, 70.0, 60.0, [], 2.0, ["Test adjustment"]
    )
    
    assert len(explanations) > 0
    assert any(e.type == "fairness" for e in explanations)