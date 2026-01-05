from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
import os, shutil
from database import Base, SessionLocal, engine
from models import QuestionPaper, Question, Student, Result, QuestionResult
from ocr_utils import extract_text
from nlp_utils import embed
from scoring import similarity_score, calculate_marks

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Question & Answer PDF/Image Evaluation")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------------------
# 1️⃣ Upload question paper PDF/IMAGE
# -------------------------------
import re
from models import QuestionPaper, Question

@app.post("/upload-question-paper/")
async def upload_question_paper(
    paper_name: str = Form(...),
    question_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        # 1️⃣ Save file
        file_path = os.path.join(UPLOAD_DIR, question_file.filename)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(question_file.file, f)

        # 2️⃣ Extract text (OCR / DOC / PDF)
        extracted_text = extract_text(file_path)
        print(extracted_text)
        if not extracted_text:
            raise HTTPException(400, "Text extraction failed")

        # 3️⃣ Save question paper
        paper = QuestionPaper(paper_name=paper_name, file_path=file_path)
        db.add(paper)
        db.commit()
        db.refresh(paper)

        # 4️⃣ Extract questions + model answers
        qa_pairs = extract_qa_pairs(extracted_text)

        print("QA PAIRS FOUND:", len(qa_pairs))
        print(qa_pairs)

        if not qa_pairs:
            print("⚠️ QA pattern failed, falling back to question-only extraction")

            # fallback: question only
            questions = re.split(
                r"(?:Q\s*)?(\d{1,2})\s*[\.\)]\s*",
                extracted_text,
                flags=re.IGNORECASE
            )

            qa_pairs = []
            for i in range(1, len(questions) - 1, 2):
                qa_pairs.append(
                    (int(questions[i]), questions[i+1].strip(), "", 10)
                )

        questions_saved = 0

        for q_no, q_text, model_ans, max_marks in qa_pairs:
            question = Question(
                paper_id=paper.id,
                question_no=q_no,
                question_text=q_text,
                model_answer=model_ans,
                max_marks=max_marks
            )
            db.add(question)
            questions_saved += 1

        db.commit()

        return {
            "paper_id": paper.id,
            "paper_name": paper.paper_name,
            "questions_saved": questions_saved
        }

    except Exception as e:
        print(e)
        raise HTTPException(500, str(e))

import re

def extract_qa_pairs(text: str):

    # Normalize text
    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"\n{2,}", "\n", text)

    pattern = re.compile(
        r"(?:Q\s*)?(\d{1,2})\s*[\.\)]\s*"      # Q number
        r"([\s\S]*?)"                          # Question text (SAFE)
        r"\s*(?:Ans|Answer|ANS|A)\s*[:\-]\s*"  # Answer keyword
        r"([\s\S]*?)"                          # Answer text
        r"(?=\n\s*(?:Q\s*)?\d{1,2}\s*[\.\)]|\Z)",
        re.IGNORECASE
    )

    results = []

    for m in pattern.finditer(text):
        q_no = int(m.group(1))
        question = m.group(2).strip()
        answer = m.group(3).strip()

        # Extract marks from question
        marks_match = re.search(r"(\d+)\s*(marks|mark|m)", question, re.IGNORECASE)
        max_marks = int(marks_match.group(1)) if marks_match else 10

        # Remove marks from question text
        question = re.sub(
            r"\(?\d+\s*(marks|mark|m)\)?",
            "",
            question,
            flags=re.IGNORECASE
        ).strip()

        results.append((q_no, question, answer, max_marks))

    return results


# -------------------------------
# 2️⃣ Upload student answer sheet
# -------------------------------
@app.post("/evaluate-answer-sheet/")
async def evaluate_answer_sheet(
    roll_number: str = Form(...),
    paper_id: int = Form(...),
    answer_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    paper = db.query(QuestionPaper).filter_by(id=paper_id).first()
    if not paper:
        raise HTTPException(404, "Invalid paper ID")

    questions = db.query(Question).filter_by(paper_id=paper_id).order_by(Question.question_no).all()
    if not questions:
        raise HTTPException(404, "No questions for this paper")

    # Save student file
    file_path = os.path.join(UPLOAD_DIR, answer_file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(answer_file.file, f)

    # OCR student answers
    student_text = extract_text(file_path)

    # Student record
    student = db.query(Student).filter_by(roll_number=roll_number).first()
    if not student:
        student = Student(roll_number=roll_number)
        db.add(student)
        db.commit()
        db.refresh(student)

    # Create overall result
    result = Result(student_id=student.id, paper_id=paper_id, total_marks=0)
    db.add(result)
    db.commit()
    db.refresh(result)

    total = 0
    question_results = []

    for q in questions:
        # Compare student answer with model answer if available
        if q.model_answer:
            sim = similarity_score(embed(q.model_answer), embed(student_text))
            marks = calculate_marks(sim, q.max_marks)
        else:
            sim = 0
            marks = 0

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
        "total_marks": result.total_marks,
        "question_wise_marks": question_results
    }
