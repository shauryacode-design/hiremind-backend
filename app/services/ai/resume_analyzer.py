from app.schemas.resume import ResumeAnalysis
from app.services.ai.ai_provider import generate_structured

def analyze_resume(resume_text: str) -> ResumeAnalysis:

    prompt = f"""
You are a professional technical recruiter and resume analyst.

Analyze the resume below.

Extract only information supported by the resume.
Do not invent skills, experience, education, projects, certifications,
achievements, or other facts.

For weaknesses, identify reasonable areas that may need further evaluation,
but do not make unsupported personal judgments.

For interview_focus_areas, identify specific topics from this resume that
should be explored during an interview.

Resume:
----------------
{resume_text}
----------------
"""

    return generate_structured(
        prompt,
        ResumeAnalysis
    )