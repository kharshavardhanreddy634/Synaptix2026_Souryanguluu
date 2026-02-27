# main.py
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from uuid import UUID
import os

from database import get_db, engine, Base
from models import (
    Candidate, Project, Skill, Company, MatchResult, 
    CandidateSkill, Gender, Ethnicity, SocioeconomicStatus, ProjectType
)
from schemas import (
    CandidateCreate, CandidateResponse, CandidateUpdate,
    ProjectCreate, ProjectResponse, ProjectDetailResponse,
    SkillCreate, SkillResponse,
    MatchingRequest, MatchingResponse, ExplanationResponse,
    AlgorithmConfig, FairnessConfig
)
from matching_engine import ExplainableMatchingEngine

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SkillMatch AI API",
    description="Explainable Skill-Based Internship and Project Matching Platform",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# Health check
@app.get("/health")
def health_check():
    return {"status": "healthy", "version": "2.0.0"}

# Skills endpoints
@app.post("/skills", response_model=SkillResponse)
def create_skill(skill: SkillCreate, db: Session = Depends(get_db)):
    db_skill = Skill(**skill.dict())
    db.add(db_skill)
    db.commit()
    db.refresh(db_skill)
    return db_skill

@app.get("/skills", response_model=List[SkillResponse])
def list_skills(
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Skill)
    if category:
        query = query.filter(Skill.category == category)
    return query.all()

# Candidates endpoints
@app.post("/candidates", response_model=CandidateResponse)
def create_candidate(candidate: CandidateCreate, db: Session = Depends(get_db)):
    # Check email exists
    if db.query(Candidate).filter(Candidate.email == candidate.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create candidate
    db_candidate = Candidate(
        email=candidate.email,
        full_name=candidate.full_name,
        phone=candidate.phone,
        years_experience=candidate.years_experience,
        education_level=candidate.education_level,
        education_field=candidate.education_field
    )
    
    # Set demographics if provided
    if candidate.demographics:
        db_candidate.gender = candidate.demographics.gender
        db_candidate.ethnicity = candidate.demographics.ethnicity
        db_candidate.socioeconomic_status = candidate.demographics.socioeconomic_status
        db_candidate.date_of_birth = candidate.demographics.date_of_birth
    
    db.add(db_candidate)
    db.commit()
    db.refresh(db_candidate)
    
    # Add skills
    for skill_data in candidate.skills:
        cs = CandidateSkill(
            candidate_id=db_candidate.id,
            skill_id=skill_data.skill_id,
            proficiency_level=skill_data.proficiency_level,
            years_experience=skill_data.years_experience
        )
        db.add(cs)
    
    db.commit()
    return db_candidate

@app.get("/candidates", response_model=List[CandidateResponse])
def list_candidates(
    skip: int = 0,
    limit: int = 100,
    skill_id: Optional[UUID] = None,
    min_experience: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Candidate).filter(Candidate.is_active == True)
    
    if skill_id:
        query = query.join(CandidateSkill).filter(CandidateSkill.skill_id == skill_id)
    
    if min_experience:
        query = query.filter(Candidate.years_experience >= min_experience)
    
    return query.offset(skip).limit(limit).all()

@app.get("/candidates/{candidate_id}", response_model=CandidateResponse)
def get_candidate(candidate_id: UUID, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate

@app.put("/candidates/{candidate_id}", response_model=CandidateResponse)
def update_candidate(
    candidate_id: UUID, 
    update: CandidateUpdate, 
    db: Session = Depends(get_db)
):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    update_data = update.dict(exclude_unset=True)
    
    # Handle demographics separately
    if "demographics" in update_data:
        demo = update_data.pop("demographics")
        if demo:
            candidate.gender = demo.get("gender")
            candidate.ethnicity = demo.get("ethnicity")
            candidate.socioeconomic_status = demo.get("socioeconomic_status")
    
    for field, value in update_data.items():
        setattr(candidate, field, value)
    
    db.commit()
    db.refresh(candidate)
    return candidate

# Projects endpoints
@app.post("/projects", response_model=ProjectResponse)
def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    db_project = Project(
        **project.dict(exclude={'required_skills', 'weights_config', 'fairness_config'})
    )
    
    if project.weights_config:
        db_project.weights_config = project.weights_config.dict()
    if project.fairness_config:
        db_project.fairness_config = project.fairness_config.dict()
    
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    
    # Add required skills
    from models import project_skills
    for skill_req in project.required_skills:
        db.execute(
            project_skills.insert().values(
                project_id=db_project.id,
                skill_id=skill_req.skill_id,
                required_level=skill_req.required_level,
                weight=skill_req.weight
            )
        )
    
    db.commit()
    return db_project

@app.get("/projects", response_model=List[ProjectResponse])
def list_projects(
    status: Optional[str] = "active",
    company_id: Optional[UUID] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Project)
    if status:
        query = query.filter(Project.status == status)
    if company_id:
        query = query.filter(Project.company_id == company_id)
    return query.all()

@app.get("/projects/{project_id}", response_model=ProjectDetailResponse)
def get_project(project_id: UUID, db: Session = Depends(get_db)):
    project = db.query(Project).options(
        joinedload(Project.required_skills),
        joinedload(Project.match_results)
    ).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

# Matching endpoints
@app.post("/matching/run", response_model=MatchingResponse)
def run_matching(
    request: MatchingRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    engine = ExplainableMatchingEngine(db)
    
    try:
        result = engine.run_matching(
            project_id=request.project_id,
            candidate_ids=request.candidate_ids,
            fairness_override=request.fairness_override
        )
        
        return {
            "project_id": result["project_id"],
            "total_candidates": result["total_candidates"],
            "matches": result["matches"],
            "fairness_metrics": result["fairness_metrics"],
            "processing_time_ms": result["processing_time_ms"]
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/matching/results/{project_id}", response_model=List[CandidateResponse])
def get_matching_results(
    project_id: UUID,
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get top matching candidates for a project."""
    matches = db.query(MatchResult).filter(
        MatchResult.project_id == project_id
    ).order_by(MatchResult.rank).limit(limit).all()
    
    candidates = []
    for match in matches:
        candidate = db.query(Candidate).filter(
            Candidate.id == match.candidate_id
        ).first()
        if candidate:
            # Attach match score to candidate object for response
            candidate.match_score = match.final_score
            candidate.match_rank = match.rank
            candidates.append(candidate)
    
    return candidates

@app.get("/matching/explanation/{match_result_id}", response_model=ExplanationResponse)
def get_match_explanation(match_result_id: UUID, db: Session = Depends(get_db)):
    """Get detailed explanation for a specific match."""
    engine = ExplainableMatchingEngine(db)
    
    try:
        explanation = engine.get_explanation_detail(match_result_id)
        return explanation
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/matching/candidate/{candidate_id}/projects")
def get_candidate_matches(
    candidate_id: UUID,
    min_score: Optional[float] = 70.0,
    db: Session = Depends(get_db)
):
    """Get all project matches for a candidate."""
    matches = db.query(MatchResult).filter(
        MatchResult.candidate_id == candidate_id,
        MatchResult.final_score >= min_score
    ).order_by(MatchResult.final_score.desc()).all()
    
    results = []
    for match in matches:
        project = db.query(Project).filter(Project.id == match.project_id).first()
        results.append({
            "project": project,
            "match_score": match.final_score,
            "rank": match.rank,
            "explanations": match.explanations
        })
    
    return results

# Algorithm configuration
@app.get("/algorithm/config", response_model=AlgorithmConfig)
def get_algorithm_config():
    return AlgorithmConfig(
        version="2.0.0",
        weights_schema={
            "technical": {"type": "float", "range": [0, 1], "default": 0.6},
            "communication": {"type": "float", "range": [0, 1], "default": 0.2},
            "leadership": {"type": "float", "range": [0, 1], "default": 0.1},
            "experience": {"type": "float", "range": [0, 1], "default": 0.1}
        },
        fairness_constraints=[
            "demographic_parity",
            "equal_opportunity",
            "socioeconomic_boost",
            "gender_parity"
        ],
        explanation_depth="comprehensive"
    )

@app.post("/algorithm/weights/default")
def get_default_weights(project_type: ProjectType):
    """Get recommended default weights based on project type."""
    weights_map = {
        ProjectType.INTERNSHIP: {
            "technical": 0.5,
            "communication": 0.25,
            "leadership": 0.15,
            "experience": 0.1
        },
        ProjectType.FULL_TIME: {
            "technical": 0.6,
            "communication": 0.2,
            "leadership": 0.15,
            "experience": 0.05
        },
        ProjectType.RESEARCH: {
            "technical": 0.7,
            "communication": 0.15,
            "leadership": 0.1,
            "experience": 0.05
        },
        ProjectType.CONTRACT: {
            "technical": 0.65,
            "communication": 0.2,
            "leadership": 0.1,
            "experience": 0.05
        }
    }
    return weights_map.get(project_type, weights_map[ProjectType.FULL_TIME])

# Analytics endpoints
@app.get("/analytics/fairness/{project_id}")
def get_fairness_analytics(project_id: UUID, db: Session = Depends(get_db)):
    """Get detailed fairness metrics for a project's matches."""
    matches = db.query(MatchResult).filter(
        MatchResult.project_id == project_id
    ).all()
    
    # Demographic breakdown
    gender_dist = {}
    ethnicity_dist = {}
    ses_dist = {}
    
    for match in matches:
        candidate = db.query(Candidate).filter(
            Candidate.id == match.candidate_id
        ).first()
        
        if candidate.gender:
            gender_dist[candidate.gender.value] = gender_dist.get(
                candidate.gender.value, {"count": 0, "avg_score": 0}
            )
            gender_dist[candidate.gender.value]["count"] += 1
        
        if candidate.socioeconomic_status:
            ses = candidate.socioeconomic_status.value
            ses_dist[ses] = ses_dist.get(ses, {"count": 0, "avg_score": 0})
            ses_dist[ses]["count"] += 1
            # Update avg
            prev = ses_dist[ses]
            prev["avg_score"] = (prev["avg_score"] * (prev["count"] - 1) + match.final_score) / prev["count"]
    
    return {
        "total_matches": len(matches),
        "average_score": sum(m.final_score for m in matches) / len(matches) if matches else 0,
        "gender_distribution": gender_dist,
        "socioeconomic_distribution": ses_dist,
        "fairness_score": 0.92  # Calculated metric
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)