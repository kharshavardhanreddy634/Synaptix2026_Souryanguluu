# seed_data.py
"""
Script to seed initial data for testing.
Run: python seed_data.py
"""

from database import SessionLocal, engine, Base
from models import (
    Candidate, Project, Skill, Company, CandidateSkill,
    Gender, Ethnicity, SocioeconomicStatus, ProjectType
)
from uuid import uuid4

def seed_data():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    try:
        # Create skills
        skills_data = [
            ("Python", "technical", "Programming language"),
            ("Machine Learning", "technical", "ML algorithms and frameworks"),
            ("Data Analysis", "technical", "Statistical analysis"),
            ("Communication", "soft", "Verbal and written communication"),
            ("Leadership", "soft", "Team leadership"),
            ("SQL", "technical", "Database querying"),
            ("Cloud Computing", "technical", "AWS/Azure/GCP"),
            ("Statistics", "technical", "Statistical methods"),
            ("Project Management", "soft", "Project planning"),
            ("Deep Learning", "technical", "Neural networks")
        ]
        
        skills = {}
        for name, category, desc in skills_data:
            skill = Skill(id=uuid4(), name=name, category=category, description=desc)
            db.add(skill)
            skills[name] = skill
        
        db.commit()
        
        # Create company
        company = Company(
            id=uuid4(),
            name="TechCorp Labs",
            description="Leading AI research company",
            industry="Technology"
        )
        db.add(company)
        db.commit()
        
        # Create project
        project = Project(
            id=uuid4(),
            title="AI Research Intern",
            company_id=company.id,
            description="Research-focused internship",
            type=ProjectType.INTERNSHIP,
            weights_config={
                "technical": 0.6,
                "communication": 0.2,
                "leadership": 0.1,
                "experience": 0.1
            },
            fairness_config={
                "demographic_parity_threshold": 0.8,
                "equal_opportunity_weight": 0.75,
                "socioeconomic_boost": True,
                "gender_parity": True,
                "blind_screening": False
            }
        )
        db.add(project)
        
        # Add required skills to project
        from models import project_skills
        db.execute(project_skills.insert().values(
            project_id=project.id,
            skill_id=skills["Python"].id,
            required_level=90,
            weight=1.5
        ))
        db.execute(project_skills.insert().values(
            project_id=project.id,
            skill_id=skills["Machine Learning"].id,
            required_level=85,
            weight=2.0
        ))
        db.execute(project_skills.insert().values(
            project_id=project.id,
            skill_id=skills["Communication"].id,
            required_level=70,
            weight=1.0
        ))
        
        # Create candidates
        candidates_data = [
            {
                "name": "Alex Chen",
                "email": "alex@example.com",
                "gender": Gender.NON_BINARY,
                "ethnicity": Ethnicity.ASIAN,
                "ses": SocioeconomicStatus.MEDIUM,
                "skills": [("Python", 95), ("Machine Learning", 88), ("Communication", 78)]
            },
            {
                "name": "Maria Garcia",
                "email": "maria@example.com",
                "gender": Gender.FEMALE,
                "ethnicity": Ethnicity.HISPANIC,
                "ses": SocioeconomicStatus.LOW,
                "skills": [("Python", 82), ("Machine Learning", 85), ("Communication", 92)]
            },
            {
                "name": "James Wilson",
                "email": "james@example.com",
                "gender": Gender.MALE,
                "ethnicity": Ethnicity.CAUCASIAN,
                "ses": SocioeconomicStatus.HIGH,
                "skills": [("Python", 88), ("Machine Learning", 75), ("Communication", 85)]
            }
        ]
        
        for cand_data in candidates_data:
            candidate = Candidate(
                id=uuid4(),
                email=cand_data["email"],
                full_name=cand_data["name"],
                gender=cand_data["gender"],
                ethnicity=cand_data["ethnicity"],
                socioeconomic_status=cand_data["ses"],
                years_experience=3
            )
            db.add(candidate)
            db.commit()
            
            # Add skills
            for skill_name, level in cand_data["skills"]:
                cs = CandidateSkill(
                    id=uuid4(),
                    candidate_id=candidate.id,
                    skill_id=skills[skill_name].id,
                    proficiency_level=level
                )
                db.add(cs)
        
        db.commit()
        print("✅ Database seeded successfully!")
        
    except Exception as e:
        print(f"❌ Error seeding data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()