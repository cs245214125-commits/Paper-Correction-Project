from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
import os, shutil

from database import SessionLocal, engine, Base
from models import (
    QuestionPaper, Question,
    Student, Result, QuestionResult
)
from ocr_utils import extract_text
from nlp_utils import embed
from scoring import similarity_score, calculate_marks

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Question Paper Based Answer Evaluation")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -----------------------------------
# 1️⃣ CREATE QUESTION PAPER
# -----------------------------------
@app.post("/create-question-paper/")
def create_question_paper(
    paper_name: str = Form(...),
    db: Session = Depends(get_db)
):
    paper = QuestionPaper(paper_name=paper_name)
    db.add(paper)
    db.commit()
    db.refresh(paper)
    return {"paper_id": paper.id, "paper_name": paper.paper_name}

# -----------------------------------
# 2️⃣ ADD QUESTIONS (ORDER PRESERVED)
# -----------------------------------
@app.post("/add-question/")
def add_question(
    paper_id: int = Form(...),
    question_no: int = Form(...),   # 1,2,3...
    question_text: str = Form(...),
    model_answer: str = Form(...),
    max_marks: int = Form(...),
    db: Session = Depends(get_db)
):
    paper = db.query(QuestionPaper).filter_by(id=paper_id).first()
    if not paper:
        raise HTTPException(404, "Invalid question paper ID")

    # ensure unique question number per paper
    exists = db.query(Question).filter_by(
        paper_id=paper_id,
        question_no=question_no
    ).first()
    if exists:
        raise HTTPException(400, "Question number already exists")

    q = Question(
        paper_id=paper_id,
        question_no=question_no,
        question_text=question_text,
        model_answer=model_answer,
        max_marks=max_marks
    )
    db.add(q)
    db.commit()

    return {"message": f"Question Q{question_no} added"}

# -----------------------------------
# 3️⃣ EVALUATE ANSWER SHEET (VALIDATED)
# -----------------------------------
@app.post("/evaluate-answer-sheet/")
async def evaluate_answer_sheet(
    roll_number: str = Form(...),
    paper_id: int = Form(...),
    answer_sheet: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    paper = db.query(QuestionPaper).filter_by(id=paper_id).first()
    if not paper:
        raise HTTPException(404, "Invalid question paper ID")

    questions = db.query(Question)\
        .filter_by(paper_id=paper_id)\
        .order_by(Question.question_no).all()

    if not questions:
        raise HTTPException(400, "No questions found for this paper")

    # Save answer sheet
    path = os.path.join(UPLOAD_DIR, answer_sheet.filename)
    with open(path, "wb") as f:
        shutil.copyfileobj(answer_sheet.file, f)

    extracted_text = extract_text(path)

    # Student check
    student = db.query(Student).filter_by(roll_number=roll_number).first()
    if not student:
        student = Student(roll_number=roll_number)
        db.add(student)
        db.commit()
        db.refresh(student)

    result = Result(student_id=student.id, paper_id=paper_id, total_marks=0)
    db.add(result)
    db.commit()
    db.refresh(result)

    total = 0
    question_results = []

    for q in questions:
        model_emb = embed(q.model_answer)
        student_emb = embed(extracted_text)

        sim = similarity_score(model_emb, student_emb)
        marks = calculate_marks(sim, q.max_marks)
        total += marks

        qr = QuestionResult(
            result_id=result.id,
            question_id=q.id,
            marks_awarded=marks,
            similarity_percentage=round(sim * 100, 2)
        )
        db.add(qr)

        question_results.append({
            "question_no": q.question_no,
            "marks_awarded": marks,
            "max_marks": q.max_marks,
            "similarity_percentage": round(sim * 100, 2)
        })

    result.total_marks = round(total, 2)
    db.commit()

    return {
        "roll_number": roll_number,
        "paper_id": paper_id,
        "paper_name": paper.paper_name,
        "total_marks": result.total_marks,
        "question_wise_marks": question_results
    }
