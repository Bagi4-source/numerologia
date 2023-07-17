from datetime import datetime
from typing import Annotated
from fastapi import APIRouter
from sqlalchemy.orm import Session
from fastapi import Depends, FastAPI, HTTPException, Form, UploadFile, File
import schemas
import crud
from database import SessionLocal

api_router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@api_router.get("/videos/", tags=['main_screen'], response_model=schemas.Videos)
async def videos(
        db: Annotated[Session, Depends(get_db)],
        offset: int,
        limit: int,
        lang: str = "en"
):
    total, query = crud.get_videos(db, offset, limit, lang)
    return {
        "videos": query,
        "count": query.count(),
        "total": total
    }


@api_router.get("/faqs/", tags=['main_screen'], response_model=schemas.FaQs)
async def faqs(
        db: Annotated[Session, Depends(get_db)],
        offset: int,
        limit: int,
        lang: str = "en"
):
    total, query = crud.get_questions(db, offset, limit, lang)
    return {
        "questions": query,
        "count": query.count(),
        "total": total
    }


@api_router.get("/faqs/{faq_id}", tags=['main_screen'], response_model=schemas.FaQDetail)
async def fsq(
        db: Annotated[Session, Depends(get_db)],
        faq_id: int,
        lang: str = "en"
):
    return crud.get_question_by_id(db, faq_id, lang)


@api_router.get("/number/", tags=['main_screen'], response_model=schemas.NumbersBase | None)
async def number(
        db: Annotated[Session, Depends(get_db)],
        date: str,
        lang: str = "en"
):
    try:
        valid_date = datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date")
    return crud.get_number(db, valid_date, lang)
