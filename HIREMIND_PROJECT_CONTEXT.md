HireMind — Project Context & Development Plan
1. Project Overview

HireMind is an AI-powered mock interview platform.

The goal is not to make a simple chatbot that asks predefined interview questions.

HireMind should behave like a professional AI interviewer that:

understands the candidate's resume
understands the target job role
creates a personalized interview
asks relevant questions
accepts spoken answers
evaluates answers intelligently
asks follow-up questions when appropriate
adapts the interview based on the candidate's responses
provides a professional final evaluation
Core interview experience
User selects target role
        ↓
Upload Resume
        ↓
PDF text extraction
        ↓
AI Resume Analysis
        ↓
Interview Planner
        ↓
Personalized Interview
        ↓
AI asks question
        ↓
Text → Speech
        ↓
Candidate hears question
        ↓
Candidate speaks answer
        ↓
Speech → Text
        ↓
AI evaluates answer
        ↓
AI decides next question / follow-up
        ↓
Continue interview
        ↓
Final evaluation
        ↓
Results dashboard
2. Product Vision

HireMind should feel closer to a real interview simulator than a student demo.

The AI interviewer should:

use the candidate's actual resume
ask role-specific questions
avoid repeatedly asking generic questions
increase/decrease difficulty based on performance
ask follow-up questions based on previous answers
detect weak or incomplete answers
challenge the candidate when appropriate
evaluate technical knowledge
evaluate project understanding
eventually evaluate communication and answer quality
provide useful feedback at the end

For now, we are building a small-user professional prototype, not a large startup-scale SaaS platform.

We are prioritizing:

smart interview behavior > unnecessary infrastructure complexity.

3. Current Technology Stack
Backend
Python
FastAPI
Uvicorn
Pydantic
SQLAlchemy
PostgreSQL
pgAdmin
JWT authentication
pwdlib
python-dotenv

FastAPI's dependency injection system is being used for things such as database sessions and authentication.

AI

Currently:

Google Gemini API

We use the Google GenAI Python SDK.

Gemini structured outputs are being used so AI responses can follow Pydantic-defined schemas rather than being arbitrary text. Google's current documentation specifically supports Pydantic schemas for structured output.

Database

PostgreSQL.

SQLAlchemy is the ORM.

SQLAlchemy's current ORM supports the Mapped / mapped_column() style we're using.

Frontend

The HireMind frontend has already been developed separately and includes:

Landing page
Login
Signup
Dashboard
Resume upload
Interview screen
Results
Profile

The backend is being built to support these features.

4. Backend Architecture

Current general structure:

hiremind-backend/
│
├── app/
│   │
│   ├── main.py
│   ├── database.py
│   ├── config.py
│   │
│   ├── models/
│   │   ├── user.py
│   │   ├── resume.py
│   │   └── interview.py
│   │
│   ├── schemas/
│   │   ├── user.py
│   │   ├── interview.py
│   │   └── interview_plan.py
│   │
│   ├── routers/
│   │   ├── user.py
│   │   ├── resume.py
│   │   └── interview.py
│   │
│   ├── services/
│   │   ├── resume_parser.py
│   │   │
│   │   └── ai/
│   │       ├── gemini.py
│   │       ├── resume_analyzer.py
│   │       └── interview_planner.py
│   │
│   └── utils/
│       └── security.py
│
├── uploads/
│   └── resumes/
│
├── .env
└── ...
5. Database
Users

Current User model contains:

users
├── id
├── first_name
├── last_name
├── email
├── hashed_password
└── created_at

Passwords are never stored directly.

They are hashed using pwdlib.

6. Authentication

Implemented:

Signup
   ↓
Password hashing
   ↓
Database


Login
   ↓
Verify password
   ↓
JWT access token
   ↓
Authenticated requests

security.py currently contains:

hash_password()
verify_password()
create_access_token()
verify_access_token()
get_current_user()

The security module is located at:

app/utils/security.py

Important: Do not move it to app/security.py unless we deliberately redesign the architecture.

7. Resume System

Implemented:

POST /resume/upload

The backend:

validates PDF
validates MIME type
generates unique filename
saves PDF
extracts text
saves resume information in PostgreSQL

Resume table:

resumes
├── id
├── user_id
├── filename
├── file_path
├── extracted_text
└── analysis
8. Resume Analysis

Gemini analyzes extracted resume text.

The output is structured into:

professional_profile
technical_skills
education
work_experience
projects
certifications
strengths
weaknesses
suitable_job_roles
interview_focus_areas

The analysis is now saved in PostgreSQL.

Flow:

PDF
 ↓
Extract text
 ↓
Gemini
 ↓
Structured ResumeAnalysis
 ↓
resume.analysis
 ↓
PostgreSQL

This is important because the interview system can reuse the analysis without unnecessarily analyzing the resume again.

9. Interview System — Current State

The Interview model now stores:

interviews
├── id
├── user_id
├── resume_id
├── target_role
├── status
├── interview_plan
└── created_at

The interview creation endpoint is:

POST /interviews/

It currently:

authenticates the user
verifies the resume belongs to the user
verifies the resume has been analyzed
sends the saved resume analysis to the Interview Planner
generates an interview plan
saves the plan to PostgreSQL
10. Interview Planner

Current file:

app/services/ai/interview_planner.py

It receives:

target_role
+
resume_analysis

and generates:

interview_strategy
+
questions[]

Each question contains:

question
topic
difficulty

Example:

{
  "question": "Explain the JavaScript event loop.",
  "topic": "JavaScript Fundamentals",
  "difficulty": "Easy"
}

The planner has already been tested successfully.

11. Important AI Design Principle

HireMind should not simply generate 10 questions and ask them blindly.

The long-term interview engine should work more like:

Question
   ↓
Candidate Answer
   ↓
Evaluate
   ↓
Determine:
- correct?
- incomplete?
- confused?
- strong?
- needs follow-up?
   ↓
Choose next action

Possible actions:

ASK_FOLLOW_UP
ASK_NEW_TOPIC
INCREASE_DIFFICULTY
DECREASE_DIFFICULTY
CLARIFY
END_INTERVIEW

This is what will make HireMind feel like an interviewer rather than a question generator.

12. RAG

RAG is planned for a later stage.

Potential architecture:

Resume
 ↓
Chunking
 ↓
Embeddings
 ↓
Vector Database
 ↓
Relevant resume sections
 ↓
Gemini

The purpose is to allow HireMind to retrieve relevant parts of a long resume when generating questions or evaluating answers.

However:

Do not introduce RAG prematurely.

The current structured resume analysis is sufficient for the first working interview engine.

RAG should be added when the basic interview workflow is working.

13. Voice System

Voice is an important requirement.

The final interview should work approximately like:

Gemini generates question
        ↓
Text-to-Speech
        ↓
AI speaks question
        ↓
Candidate speaks
        ↓
Speech-to-Text
        ↓
Transcript
        ↓
AI evaluates answer

The AI should therefore ask questions in voice and receive answers in voice.

But we should build the interview engine first using text.

Then add:

Speech-to-text
Text-to-speech
Frontend microphone handling
Real-time/streaming improvements if needed

This keeps the architecture manageable.

14. Planned Interview Engine

This is the next major backend component.

We need something approximately like:

Interview
│
├── current_question
├── question_number
├── conversation/history
├── candidate_answers
├── evaluations
└── interview_status

The interview engine should eventually support:

START
 ↓
Question 1
 ↓
Answer
 ↓
Evaluate
 ↓
Question 2 / Follow-up
 ↓
Answer
 ↓
Evaluate
 ↓
...
 ↓
FINAL EVALUATION
15. Planned Answer Evaluation

Gemini should evaluate answers based on the question and candidate's context.

Potential evaluation:

score
technical_accuracy
relevance
completeness
clarity
strengths
weaknesses
feedback

For technical questions, evaluation should focus primarily on correctness rather than judging English fluency.

16. Planned Adaptive Interview

Eventually:

Strong answer
    ↓
Increase difficulty


Weak answer
    ↓
Follow-up / clarification


Incomplete answer
    ↓
Probe deeper


Excellent answer
    ↓
Move to harder topic

The interviewer should also consider:

target role
resume
previous questions
previous answers
previous evaluations
interview progress
17. Final Interview Evaluation

At the end:

Interview
 ↓
All questions
 ↓
All answers
 ↓
All evaluations
 ↓
Gemini
 ↓
Final Report

Potential report:

Overall Score
Technical Knowledge
Problem Solving
Communication
Project Knowledge
Role Readiness


Strengths
Weaknesses
Recommended Topics
Interview Summary
18. Future Frontend Integration

Once the backend interview engine works:

Dashboard
 ↓
Choose resume
 ↓
Choose target role
 ↓
Start Interview
 ↓
Interview screen
 ↓
Question appears / speaks
 ↓
Microphone
 ↓
Candidate answers
 ↓
Next question
 ↓
...
 ↓
Results

The existing frontend should then be connected to these backend APIs.

19. Development Order

This is the order we should follow.

Phase 1 — Foundation
Database                         ✅
User model                       ✅
Signup                           ✅
Login                            ✅
Password hashing                ✅
JWT                              ✅
Current user                     ✅
Phase 2 — Resume
Resume upload                    ✅
PDF extraction                   ✅
Resume database                  ✅
Gemini resume analysis           ✅
Structured analysis              ✅
Save analysis                    ✅
Phase 3 — Interview Planning
Interview model                  ✅
Interview schema                 ✅
Interview creation               ✅
Interview planner                ✅
Personalized questions           ✅
Save interview plan              ✅
Phase 4 — Actual Interview Engine
Start interview                  ← CURRENT AREA
Get next question
Submit answer
Evaluate answer
Generate follow-up
Adaptive questioning
Interview history
End interview
Phase 5 — Results
Final evaluation
Overall score
Strengths
Weaknesses
Recommendations
Results API
Phase 6 — Voice
Speech-to-text
Text-to-speech
Microphone
Audio playback
Voice interview flow
Phase 7 — RAG / Advanced AI
Resume chunking
Embeddings
Vector database
Retrieval
Resume-grounded questioning
Better contextual follow-ups
Phase 8 — Production Hardening
Error handling
Rate limiting
Logging
Database migrations
API security
AI failure handling
Gemini fallback strategy
File security
Testing
Deployment
Monitoring
20. What We Should NOT Do Yet

To prevent the project becoming unnecessarily complicated:

Don't add yet:

RAG
vector database
WebSockets
complicated agent frameworks
microservices
Redis
Celery
Kubernetes
payment system
multi-model orchestration
complex real-time infrastructure

First make this work:

Upload resume
      ↓
Analyze resume
      ↓
Create interview
      ↓
Ask question
      ↓
Receive answer
      ↓
Evaluate
      ↓
Ask next question
      ↓
Finish
      ↓
Generate report

Then improve it.

21. Current Exact Position

This is the most important part for continuing in a new chat.

We are currently here:
                    HIREMIND


Authentication                 ✅
      ↓
Resume Upload                  ✅
      ↓
PDF Extraction                 ✅
      ↓
Gemini Resume Analysis         ✅
      ↓
Save Analysis                  ✅
      ↓
Interview Creation             ✅
      ↓
Gemini Interview Planner       ✅
      ↓
Save Interview Plan            ✅
      ↓
────────────────────────────────────
      ↓
     NEXT
      ↓
ACTUAL INTERVIEW ENGINE
      ↓
Question → Answer → Evaluation
      ↓
Adaptive Follow-up
      ↓
Final Evaluation
      ↓
Voice
      ↓
RAG / Advanced improvements
Exact next task

We were about to test the real /interviews/ endpoint with:

{
  "resume_id": 1,
  "target_role": "Data Analyst"
}

The endpoint should generate and save the personalized interview plan.

After that, we move into the actual interview engine.