from sqlalchemy import Column, Integer, String, Text, ForeignKey, Float
from database import Base
from sqlalchemy import Column, String

class QuestionPaper(Base):
    __tablename__ = "question_papers"

    id = Column(Integer, primary_key=True)
    paper_name = Column(String, nullable=False)

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True)
    paper_id = Column(Integer, ForeignKey("question_papers.id"))
    question_no = Column(String(10))  # 10 is max length; adjust as needed
    question_text = Column(Text, nullable=False)
    model_answer = Column(Text, nullable=False)
    max_marks = Column(Integer, nullable=False)

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True)
    roll_number = Column(String, unique=True, nullable=False)

class Result(Base):
    __tablename__ = "results"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    paper_id = Column(Integer, ForeignKey("question_papers.id"))
    total_marks = Column(Float)

class QuestionResult(Base):
    __tablename__ = "question_results"

    id = Column(Integer, primary_key=True)
    result_id = Column(Integer, ForeignKey("results.id"))
    question_id = Column(Integer, ForeignKey("questions.id"))
    marks_awarded = Column(Float)
    similarity_percentage = Column(Float)
