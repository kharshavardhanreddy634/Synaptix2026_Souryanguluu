# matching_engine.py
import numpy as np
from typing import List, Dict, Tuple, Any
from models import Candidate, Project, MatchResult, CandidateSkill
from schemas import SkillGap, ExplanationItem, FairnessConfig
from sqlalchemy.orm import Session
import time
from datetime import datetime

class ExplainableMatchingEngine:
    """
    Core matching engine with explainable AI and fairness constraints.
    Implements weighted competency scoring with bias mitigation.
    """
    
    VERSION = "2.0.0"
    
    def __init__(self, db: Session):
        self.db = db
        self.fairness_config = None
        self.weights = None
        
    def calculate_match(
        self, 
        candidate: Candidate, 
        project: Project,
        custom_weights: Dict[str, float] = None,
        custom_fairness: FairnessConfig = None
    ) -> Dict[str, Any]:
        """
        Calculate match score with full explainability.
        """
        start_time = time.time()
        
        # Use project configs or overrides
        weights = custom_weights or project.weights_config
        fairness = custom_fairness or FairnessConfig(**project.fairness_config)
        
        # Build skill vectors
        candidate_vector = self._build_candidate_vector(candidate, project)
        required_vector = self._build_requirement_vector(project)
        
        # Calculate component scores
        technical_score = self._calculate_technical_score(
            candidate_vector, required_vector, project
        )
        communication_score = self._get_skill_score(candidate, "Communication")
        leadership_score = self._get_skill_score(candidate, "Leadership")
        experience_score = min(100, candidate.years_experience * 15)
        
        # Weighted raw score
        raw_score = (
            technical_score * weights.get('technical', 0.6) +
            communication_score * weights.get('communication', 0.2) +
            leadership_score * weights.get('leadership', 0.1) +
            experience_score * weights.get('experience', 0.1)
        )
        
        # Fairness adjustments
        fairness_bonus, bias_mitigations = self._apply_fairness_constraints(
            candidate, raw_score, fairness
        )
        
        final_score = min(100.0, raw_score + fairness_bonus)
        
        # Generate explanations
        skill_gaps = self._calculate_skill_gaps(candidate, project)
        explanations = self._generate_explanations(
            candidate, technical_score, communication_score, 
            leadership_score, experience_score, skill_gaps, 
            fairness_bonus, bias_mitigations
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        return {
            "raw_score": round(raw_score, 2),
            "final_score": round(final_score, 2),
            "fairness_adjustment": round(fairness_bonus, 2),
            "technical_score": round(technical_score, 2),
            "communication_score": round(communication_score, 2),
            "leadership_score": round(leadership_score, 2),
            "experience_score": round(experience_score, 2),
            "skill_gaps": skill_gaps,
            "explanations": explanations,
            "bias_mitigation_applied": bias_mitigations,
            "processing_time_ms": round(processing_time, 2)
        }
    
    def _build_candidate_vector(self, candidate: Candidate, project: Project) -> Dict[str, float]:
        """Build skill vector for candidate based on project requirements."""
        vector = {}
        for skill_req in project.required_skills:
            skill_name = skill_req.name
            # Find candidate's proficiency
            proficiency = self.db.query(CandidateSkill).filter(
                CandidateSkill.candidate_id == candidate.id,
                CandidateSkill.skill_id == skill_req.id
            ).first()
            
            vector[skill_name] = proficiency.proficiency_level if proficiency else 0
        
        return vector
    
    def _build_requirement_vector(self, project: Project) -> Dict[str, float]:
        """Build required skills vector from project."""
        from models import project_skills
        
        vector = {}
        for skill in project.required_skills:
            # Get requirement level from association table
            req_level = self.db.query(project_skills).filter(
                project_skills.c.project_id == project.id,
                project_skills.c.skill_id == skill.id
            ).first()
            
            vector[skill.name] = req_level.required_level if req_level else 80
        
        return vector
    
    def _calculate_technical_score(
        self, 
        candidate_vector: Dict[str, float], 
        required_vector: Dict[str, float],
        project: Project
    ) -> float:
        """Calculate weighted technical competency score."""
        scores = []
        weights = []
        
        from models import project_skills
        
        for skill_name, required_level in required_vector.items():
            actual_level = candidate_vector.get(skill_name, 0)
            
            # Get skill weight from project config
            skill_record = self.db.query(project_skills).join(
                Skill, project_skills.c.skill_id == Skill.id
            ).filter(
                project_skills.c.project_id == project.id,
                Skill.name == skill_name
            ).first()
            
            weight = skill_record.weight if skill_record else 1.0
            
            # Calculate normalized score with buffer
            if required_level > 0:
                score = min(100, (actual_level / required_level) * 100)
            else:
                score = 100 if actual_level > 0 else 0
            
            scores.append(score)
            weights.append(weight)
        
        if not scores:
            return 0
        
        # Weighted average
        return np.average(scores, weights=weights)
    
    def _get_skill_score(self, candidate: Candidate, skill_name: str) -> float:
        """Get specific skill score for candidate."""
        skill_record = self.db.query(CandidateSkill).join(
            Skill, CandidateSkill.skill_id == Skill.id
        ).filter(
            CandidateSkill.candidate_id == candidate.id,
            Skill.name == skill_name
        ).first()
        
        return skill_record.proficiency_level if skill_record else 0
    
    def _apply_fairness_constraints(
        self, 
        candidate: Candidate, 
        raw_score: float,
        config: FairnessConfig
    ) -> Tuple[float, List[str]]:
        """Apply fairness adjustments to ensure equitable outcomes."""
        bonus = 0
        mitigations = []
        
        # Socioeconomic boost
        if config.socioeconomic_boost and candidate.socioeconomic_status:
            if candidate.socioeconomic_status.value == "low":
                bonus += 3
                mitigations.append(
                    f"Socioeconomic opportunity boost applied (+3%) for "
                    f"candidate from {candidate.socioeconomic_status.value} SES background"
                )
        
        # Gender parity adjustment
        if config.gender_parity and candidate.gender:
            if candidate.gender.value in ["female", "non_binary"]:
                bonus += 2
                mitigations.append(
                    f"Gender parity adjustment (+2%) applied to promote "
                    f"diversity in {candidate.gender.value} representation"
                )
        
        # Experience normalization (prevent bias against early career)
        if candidate.years_experience < 3 and raw_score > 70:
            bonus += 1
            mitigations.append(
                "Early career potential boost (+1%) for high-performing junior candidate"
            )
        
        return bonus, mitigations
    
    def _calculate_skill_gaps(
        self, 
        candidate: Candidate, 
        project: Project
    ) -> List[SkillGap]:
        """Identify and rank skill gaps."""
        gaps = []
        
        from models import project_skills
        
        for skill in project.required_skills:
            required = self.db.query(project_skills).filter(
                project_skills.c.project_id == project.id,
                project_skills.c.skill_id == skill.id
            ).first()
            
            required_level = required.required_level if required else 80
            
            actual = self.db.query(CandidateSkill).filter(
                CandidateSkill.candidate_id == candidate.id,
                CandidateSkill.skill_id == skill.id
            ).first()
            
            actual_level = actual.proficiency_level if actual else 0
            
            if actual_level < required_level:
                gaps.append(SkillGap(
                    skill=skill.name,
                    required=required_level,
                    actual=actual_level,
                    gap=required_level - actual_level
                ))
        
        # Sort by gap size descending
        return sorted(gaps, key=lambda x: x.gap, reverse=True)
    
    def _generate_explanations(
        self,
        candidate: Candidate,
        technical: float,
        communication: float,
        leadership: float,
        experience: float,
        gaps: List[SkillGap],
        fairness_bonus: float,
        mitigations: List[str]
    ) -> List[ExplanationItem]:
        """Generate human-readable explanations for the match."""
        explanations = []
        
        # Technical competency analysis
        if technical >= 85:
            explanations.append(ExplanationItem(
                type="strength",
                category="Technical Excellence",
                detail=f"Exceptional technical alignment ({technical:.1f}%) with "
                       f"project requirements. Candidate demonstrates mastery in key areas.",
                impact="High"
            ))
        elif technical >= 70:
            explanations.append(ExplanationItem(
                type="neutral",
                category="Technical Competency",
                detail=f"Solid technical foundation ({technical:.1f}%) meets project needs.",
                impact="Medium"
            ))
        else:
            explanations.append(ExplanationItem(
                type="weakness",
                category="Technical Gap",
                detail=f"Technical skills ({technical:.1f}%) below optimal threshold. "
                       f"Consider upskilling program.",
                impact="Medium"
            ))
        
        # Soft skills
        if communication >= 85:
            explanations.append(ExplanationItem(
                type="strength",
                category="Communication",
                detail="Outstanding communication skills indicate strong team collaboration potential.",
                impact="High"
            ))
        
        if leadership >= 80:
            explanations.append(ExplanationItem(
                type="strength",
                category="Leadership",
                detail="Demonstrated leadership capability suitable for mentoring or team lead roles.",
                impact="Medium"
            ))
        
        # Skill gaps
        if gaps:
            top_gap = gaps[0]
            explanations.append(ExplanationItem(
                type="gap",
                category="Development Opportunity",
                detail=f"Primary gap in {top_gap.skill}: "
                       f"{top_gap.actual}/{top_gap.required} required. "
                       f"Recommended focus area for growth.",
                impact="Low"
            ))
        
        # Fairness adjustments
        if fairness_bonus > 0:
            explanations.append(ExplanationItem(
                type="fairness",
                category="Equity Adjustment",
                detail=f"Applied {fairness_bonus:.0f}% fairness adjustment to ensure "
                       f"demographic parity and equal opportunity.",
                impact="Adjustment"
            ))
        
        # Experience context
        if candidate.years_experience >= 5:
            explanations.append(ExplanationItem(
                type="strength",
                category="Experience",
                detail=f"{candidate.years_experience} years of industry experience "
                       f"brings valuable domain expertise.",
                impact="Medium"
            ))
        
        return explanations
    
    def run_matching(
        self, 
        project_id: UUID, 
        candidate_ids: List[UUID] = None,
        fairness_override: FairnessConfig = None
    ) -> Dict[str, Any]:
        """
        Run complete matching process for a project.
        """
        start_time = time.time()
        
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        # Get candidates
        query = self.db.query(Candidate).filter(Candidate.is_active == True)
        if candidate_ids:
            query = query.filter(Candidate.id.in_(candidate_ids))
        
        candidates = query.all()
        
        # Calculate matches
        results = []
        for candidate in candidates:
            match_data = self.calculate_match(
                candidate, project,
                custom_fairness=fairness_override
            )
            
            # Create or update match result
            match_result = MatchResult(
                candidate_id=candidate.id,
                project_id=project.id,
                raw_score=match_data["raw_score"],
                final_score=match_data["final_score"],
                fairness_adjustment=match_data["fairness_adjustment"],
                technical_score=match_data["technical_score"],
                communication_score=match_data["communication_score"],
                leadership_score=match_data["leadership_score"],
                experience_score=match_data["experience_score"],
                skill_gaps=[gap.dict() for gap in match_data["skill_gaps"]],
                explanations=[exp.dict() for exp in match_data["explanations"]],
                bias_mitigation_applied=match_data["bias_mitigation_applied"],
                algorithm_version=self.VERSION
            )
            
            self.db.add(match_result)
            results.append((candidate, match_result, match_data))
        
        self.db.commit()
        
        # Rank results
        results.sort(key=lambda x: x[1].final_score, reverse=True)
        
        for rank, (candidate, match, _) in enumerate(results, 1):
            match.rank = rank
        
        self.db.commit()
        
        # Calculate fairness metrics
        fairness_metrics = self._calculate_fairness_metrics(results)
        
        total_time = (time.time() - start_time) * 1000
        
        return {
            "project_id": project_id,
            "total_candidates": len(candidates),
            "matches": [r[1] for r in results],
            "fairness_metrics": fairness_metrics,
            "processing_time_ms": round(total_time, 2)
        }
    
    def _calculate_fairness_metrics(
        self, 
        results: List[Tuple[Candidate, MatchResult, Dict]]
    ) -> Dict[str, float]:
        """Calculate demographic parity metrics."""
        if not results:
            return {}
        
        # Group by gender
        gender_scores = {}
        for candidate, match, _ in results:
            if candidate.gender:
                gender = candidate.gender.value
                if gender not in gender_scores:
                    gender_scores[gender] = []
                gender_scores[gender].append(match.final_score)
        
        # Calculate parity
        metrics = {}
        if gender_scores:
            avg_scores = {g: np.mean(scores) for g, scores in gender_scores.items()}
            if len(avg_scores) > 1:
                max_avg = max(avg_scores.values())
                min_avg = min(avg_scores.values())
                metrics["gender_parity_ratio"] = round(min_avg / max_avg, 3) if max_avg > 0 else 1.0
        
        # Socioeconomic parity
        ses_scores = {}
        for candidate, match, _ in results:
            if candidate.socioeconomic_status:
                ses = candidate.socioeconomic_status.value
                if ses not in ses_scores:
                    ses_scores[ses] = []
                ses_scores[ses].append(match.final_score)
        
        if ses_scores:
            avg_scores = {s: np.mean(scores) for s, scores in ses_scores.items()}
            metrics["socioeconomic_parity"] = round(np.std(list(avg_scores.values())), 3)
        
        metrics["overall_fairness_score"] = round(
            1 - metrics.get("socioeconomic_parity", 0), 3
        )
        
        return metrics
    
    def get_explanation_detail(
        self, 
        match_result_id: UUID
    ) -> Dict[str, Any]:
        """Generate detailed explanation for a specific match."""
        match = self.db.query(MatchResult).filter(
            MatchResult.id == match_result_id
        ).first()
        
        if not match:
            raise ValueError("Match result not found")
        
        candidate = match.candidate
        project = match.project
        
        # Build decision tree
        decision_tree = {
            "root": {
                "stage": "Initial Assessment",
                "description": "Raw competency evaluation",
                "score": match.raw_score,
                "components": {
                    "technical": match.technical_score,
                    "communication": match.communication_score,
                    "leadership": match.leadership_score,
                    "experience": match.experience_score
                }
            },
            "fairness_layer": {
                "stage": "Fairness Correction",
                "description": "Demographic parity adjustments",
                "adjustments": match.bias_mitigation_applied,
                "bonus": match.fairness_adjustment
            },
            "final": {
                "stage": "Final Scoring",
                "description": "Normalized final match score",
                "score": match.final_score,
                "rank": match.rank
            }
        }
        
        # Build heatmap data
        heatmap = []
        for gap in match.skill_gaps:
            heatmap.append({
                "skill": gap["skill"],
                "required": gap["required"],
                "actual": gap["actual"],
                "intensity": gap["actual"] / gap["required"] if gap["required"] > 0 else 0
            })
        
        # Add skills without gaps
        candidate_skills = {cs.skill.name: cs.proficiency_level 
                          for cs in candidate.skill_proficiencies}
        for skill in project.required_skills:
            if skill.name not in [g["skill"] for g in match.skill_gaps]:
                heatmap.append({
                    "skill": skill.name,
                    "required": 80,  # Default
                    "actual": candidate_skills.get(skill.name, 0),
                    "intensity": 1.0
                })
        
        return {
            "match_id": match_result_id,
            "decision_tree": decision_tree,
            "competency_heatmap": heatmap,
            "bias_log": match.bias_mitigation_applied,
            "confidence_score": self._calculate_confidence(match)
        }
    
    def _calculate_confidence(self, match: MatchResult) -> float:
        """Calculate confidence score based on data quality."""
        factors = []
        
        # Score variance from components
        scores = [
            match.technical_score,
            match.communication_score,
            match.leadership_score,
            match.experience_score
        ]
        variance = np.var(scores)
        factors.append(max(0, 1 - variance / 1000))
        
        # Data completeness (simplified)
        factors.append(0.9)  # Placeholder
        
        return round(np.mean(factors), 3)