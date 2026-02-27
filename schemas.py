# schemas.py
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from enum import Enum
from models import Gender, Ethnicity, SocioeconomicStatus, ProjectType

# Skill Schemas
class SkillBase(BaseModel):
    name: str
    category: Optional[str] = None
    description: Optional[str] = None

class SkillCreate(SkillBase):
    pass

class SkillResponse(SkillBase):
    id: UUID
    
    class Config:
        from_attributes = True

# Candidate Schemas
class CandidateSkillBase(BaseModel):
    skill_id: UUID
    proficiency_level: int = Field(..., ge=0, le=100)
    years_experience: Optional[float] = 0

class CandidateDemographics(BaseModel):
    gender: Optional[Gender] = None
    ethnicity: Optional[Ethnicity] = None
    socioeconomic_status: Optional[SocioeconomicStatus] = None
    date_of_birth: Optional[datetime] = None

class CandidateBase(BaseModel):
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    years_experience: int = 0
    education_level: Optional[str] = None
    education_field: Optional[str] = None

class CandidateCreate(CandidateBase):
    password: str
    demographics: Optional[CandidateDemographics] = None
    skills: List[CandidateSkillBase] = []

class CandidateUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    years_experience: Optional[int] = None
    education_level: Optional[str] = None
    demographics: Optional[CandidateDemographics] = None
    is_blind_review: Optional[bool] = None

class CandidateSkillResponse(BaseModel):
    skill: SkillResponse
    proficiency_level: int
    years_experience: float
    
    class Config:
        from_attributes = True

class CandidateResponse(CandidateBase):
    id: UUID
    demographics: Optional[Dict[str, Any]] = None
    skills: List[CandidateSkillResponse] = []
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class CandidateDetailResponse(CandidateResponse):
    skill_proficiencies: List[CandidateSkillResponse] = []
    match_results: List['MatchResultResponse'] = []

# Project Schemas
class ProjectWeights(BaseModel):
    technical: float = Field(..., ge=0, le=1)
    communication: float = Field(..., ge=0, le=1)
    leadership: float = Field(..., ge=0, le=1)
    experience: float = Field(..., ge=0, le=1)

class FairnessConfig(BaseModel):
    demographic_parity_threshold: float = Field(default=0.8, ge=0, le=1)
    equal_opportunity_weight: float = Field(default=0.75, ge=0, le=1)
    socioeconomic_boost: bool = True
    gender_parity: bool = True
    blind_screening: bool = False

class ProjectSkillRequirement(BaseModel):
    skill_id: UUID
    required_level: int = Field(..., ge=0, le=100)
    weight: float = Field(default=1.0, ge=0, le=2)

class ProjectBase(BaseModel):
    title: str
    description: Optional[str] = None
    type: ProjectType
    location: Optional[str] = None
    is_remote: bool = False
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None

class ProjectCreate(ProjectBase):
    company_id: UUID
    weights_config: Optional[ProjectWeights] = None
    fairness_config: Optional[FairnessConfig] = None
    required_skills: List[ProjectSkillRequirement] = []
    deadline: Optional[datetime] = None

class ProjectResponse(ProjectBase):
    id: UUID
    company_id: UUID
    weights_config: Dict[str, float]
    fairness_config: Dict[str, Any]
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class ProjectDetailResponse(ProjectResponse):
    required_skills: List[Dict[str, Any]] = []
    match_results: List['MatchResultResponse'] = []

# Matching Schemas
class SkillGap(BaseModel):
    skill: str
    required: int
    actual: int
    gap: int

class ExplanationItem(BaseModel):
    type: str  # strength, weakness, gap, fairness
    category: str
    detail: str
    impact: str

class MatchResultBase(BaseModel):
    candidate_id: UUID
    project_id: UUID
    raw_score: float
    final_score: float
    fairness_adjustment: float
    technical_score: float
    communication_score: float
    leadership_score: float
    experience_score: float
    rank: int

class MatchResultResponse(MatchResultBase):
    id: UUID
    skill_gaps: List[SkillGap]
    explanations: List[ExplanationItem]
    bias_mitigation_applied: List[str]
    algorithm_version: str
    calculated_at: datetime
    candidate: Optional[CandidateResponse] = None
    
    class Config:
        from_attributes = True

class MatchingRequest(BaseModel):
    project_id: UUID
    candidate_ids: Optional[List[UUID]] = None  # If None, match all active candidates
    fairness_override: Optional[FairnessConfig] = None

class MatchingResponse(BaseModel):
    project_id: UUID
    total_candidates: int
    matches: List[MatchResultResponse]
    fairness_metrics: Dict[str, float]
    processing_time_ms: int

class ExplanationResponse(BaseModel):
    match_id: UUID
    decision_tree: Dict[str, Any]
    competency_heatmap: List[Dict[str, Any]]
    bias_log: List[str]
    confidence_score: float

# Algorithm Configuration
class AlgorithmConfig(BaseModel):
    version: str
    weights_schema: Dict[str, Any]
    fairness_constraints: List[str]
    explanation_depth: str  # basic, detailed, comprehensive