from pydantic import BaseModel


class ResumeAnalysis(BaseModel):
    professional_profile: str
    technical_skills: list[str]
    education: list[str]
    work_experience: list[str]
    projects: list[str]
    certifications: list[str]
    strengths: list[str]
    weaknesses: list[str]
    suitable_job_roles: list[str]
    interview_focus_areas: list[str]