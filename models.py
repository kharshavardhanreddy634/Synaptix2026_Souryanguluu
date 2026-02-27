# models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Table, Boolean, JSON, Text, Enum
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from database import Base
import uuid
from datetime import datetime
import enum

class Gender(enum.Enum):
    MALE = "male"
    FEMALE = "female"
    NON_BINARY = "non_binary"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"

class Ethnicity(enum.Enum):
    ASIAN = "asian"
    BLACK = "black"
    HISPANIC = "hispanic"
    CAUCASIAN = "caucasian"
    SOUTH_ASIAN = "south_asian"
    EAST_ASIAN = "east_asian"
    OTHER = "other"

class SocioeconomicStatus(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class ProjectType(enum.Enum):
    INTERNSHIP = "internship"
    FULL_TIME = "full_time"
    CONTRACT = "contract"
    RESEARCH = "research"

# Association tables
candidate_skills = Table(
    'candidate_skills',
    Base.metadata,
    Column('candidate_id', UUID(as_uuid=True), ForeignKey('candidates.id')),
    Column('skill_id', UUID(as_uuid=True), ForeignKey('skills.id')),
    Column('proficiency_level', Integer, default=0)
)

project_skills = Table(
    'project_skills',
    Base.metadata,
    Column('project_id', UUID(as_uuid=True), ForeignKey('projects.id')),
    Column('skill_id', UUID(as_uuid=True), ForeignKey('skills.id')),
    Column('required_level', Integer, default=0),
    Column('weight', Float, default=1.0)
)

class Skill(Base):
    __tablename__ = "skills"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, index=True, nullable=False)
    category = Column(String(50))  # technical, soft, domain
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class Candidate(Base):
    __tablename__ = "candidates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255))
    full_name = Column(String(200), nullable=False)
    phone = Column(String(20))
    
    # Demographics for fairness tracking
    gender = Column(Enum(Gender))
    ethnicity = Column(Enum(Ethnicity))
    socioeconomic_status = Column(Enum(SocioeconomicStatus))
    date_of_birth = Column(DateTime)
    
    # Professional info
    years_experience = Column(Integer, default=0)
    education_level = Column(String(100))
    education_field = Column(String(100))
    resume_url = Column(String(500))
    portfolio_url = Column(String(500))
    linkedin_url = Column(String(500))
    
    # Skills relationship
    skills = relationship("Skill", secondary=candidate_skills, backref="candidates")
    skill_proficiencies = relationship("CandidateSkill", back_populates="candidate")
    
    # Metadata
    is_active = Column(Boolean, default=True)
    is_blind_review = Column(Boolean, default=False)  # For blind screening
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    match_results = relationship("MatchResult", back_populates="candidate")

class CandidateSkill(Base):
    __tablename__ = "candidate_skill_details"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey('candidates.id'))
    skill_id = Column(UUID(as_uuid=True), ForeignKey('skills.id'))
    proficiency_level = Column(Integer, default=0)  # 0-100
    years_experience = Column(Float, default=0)
    verified = Column(Boolean, default=False)  # Skill assessment verified
    
    candidate = relationship("Candidate", back_populates="skill_proficiencies")
    skill = relationship("Skill")

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(200), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey('companies.id'))
    description = Column(Text)
    type = Column(Enum(ProjectType))
    location = Column(String(200))
    is_remote = Column(Boolean, default=False)
    salary_min = Column(Integer)
    salary_max = Column(Integer)
    
    # Matching configuration
    weights_config = Column(JSON, default={
        "technical": 0.6,
        "communication": 0.2,
        "leadership": 0.1,
        "experience": 0.1
    })
    
    # Fairness settings
    fairness_config = Column(JSON, default={
        "demographic_parity_threshold": 0.8,
        "equal_opportunity_weight": 0.75,
        "socioeconomic_boost": True,
        "gender_parity": True,
        "blind_screening": False
    })
    
    # Status
    status = Column(String(20), default="active")  # active, closed, paused
    created_at = Column(DateTime, default=datetime.utcnow)
    deadline = Column(DateTime)
    
    # Relationships
    company = relationship("Company", back_populates="projects")
    required_skills = relationship("Skill", secondary=project_skills)
    match_results = relationship("MatchResult", back_populates="project")

class Company(Base):
    __tablename__ = "companies"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    industry = Column(String(100))
    website = Column(String(500))
    logo_url = Column(String(500))
    
    projects = relationship("Project", back_populates="company")

class MatchResult(Base):
    __tablename__ = "match_results"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey('candidates.id'))
    project_id = Column(UUID(as_uuid=True), ForeignKey('projects.id'))
    
    # Scores
    raw_score = Column(Float)
    final_score = Column(Float)
    fairness_adjustment = Column(Float, default=0)
    
    # Component scores
    technical_score = Column(Float)
    communication_score = Column(Float)
    leadership_score = Column(Float)
    experience_score = Column(Float)
    
    # Explanation data
    skill_gaps = Column(JSON, default=list)
    explanations = Column(JSON, default=list)
    bias_mitigation_applied = Column(JSON, default=list)
    
    # Ranking
    rank = Column(Integer)
    
    # Audit
    algorithm_version = Column(String(20), default="1.0")
    calculated_at = Column(DateTime, default=datetime.utcnow)
    
    candidate = relationship("Candidate", back_populates="match_results")
    project = relationship("Project", back_populates="match_results")

class MatchingAlgorithmLog(Base):
    __tablename__ = "algorithm_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey('projects.id'))
    run_timestamp = Column(DateTime, default=datetime.utcnow)
    candidates_processed = Column(Integer)
    average_score = Column(Float)
    fairness_score = Column(Float)  # Demographic parity metric
    processing_time_ms = Column(Integer)
    parameters_used = Column(JSON)