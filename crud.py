import datetime
import hashlib
import random
from sqlalchemy.orm import Session, defer
import models
import schemas


def hashed_password(password: str):
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), b'germesik228', 100000, dklen=32)


def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()


def create_user(db: Session, user: schemas.UserCreate):
    try:
        db_user = models.User(
            name=user.name,
            email=user.email,
            password=str(hashed_password(user.password)),
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except:
        return


def delete_user(db: Session, user: models.User):
    try:
        db.delete(user)
        db.commit()
    except:
        return


def verify_password(user: models.User, password: str):
    return str(hashed_password(password)) == user.password


def create_token(db: Session, user_id):
    try:
        token = models.Token(
            user=user_id,
        )
        db.add(token)
        db.commit()
        db.refresh(token)
        return token
    except:
        return


def get_token(db: Session, token: str):
    try:
        return db.query(models.Token).filter(models.Token.token == token).first()
    except:
        return


def remove_token(db: Session, token: models.Token):
    try:
        db.delete(token)
        db.commit()
    except:
        return


def get_user_by_email(db: Session, email: str):
    try:
        return db.query(models.User).filter(models.User.email == email).first()
    except:
        return


def get_user_by_id(db: Session, user_id: str):
    try:
        return db.query(models.User).filter(models.User.id == user_id).first()
    except:
        return


def user_remove_tokens(db: Session, user: models.User):
    db.query(models.Token).filter(models.Token.user == user.id).delete()
    db.commit()
    db.refresh(user)


def user_update_password(db: Session, user: models.User, password: str):
    try:
        user.password = str(hashed_password(password))
        db.commit()
        db.refresh(user)
        user_remove_tokens(db, user)
    except:
        return


def user_update_name(db: Session, user: models.User, name: str):
    try:
        user.name = name
        db.commit()
        db.refresh(user)
    except:
        return


def user_update_email(db: Session, user: models.User, email: str):
    try:
        user.email = email
        db.commit()
        db.refresh(user)
        user_remove_tokens(db, user)
    except:
        return


def create_code(db: Session, user_id, step: str):
    try:
        code = models.Code(
            code=random.randint(1000, 9999),
            user=user_id,
            step=step,
        )
        db.add(code)
        db.commit()
        db.refresh(code)
        return code
    except:
        return


def update_code(db: Session, code: models.Code):
    try:
        code.code = random.randint(1000, 9999)
        code.attempts = 0
        db.commit()
        db.refresh(code)
        return code
    except:
        return


def verify_code(db: Session, codeObj: models.Code, code: str):
    if codeObj.attempts < 3:
        codeObj.attempts += 1
        db.commit()
        db.refresh(codeObj)
    else:
        remove_code(db, codeObj)
    result = code == str(codeObj.code)
    if result:
        remove_code(db, codeObj)
    return result


def get_code(db: Session, user_id, step: str):
    return db.query(models.Code).filter(models.Code.user == user_id and models.Code.step == step).order_by(
        models.Code.id.desc()).first()


def remove_code(db: Session, code: models.Code):
    try:
        db.delete(code)
        db.commit()
    except:
        return


def create_request(db: Session, step: str, user_id):
    try:
        request = models.Request(
            user=user_id,
            step=step,
        )
        db.add(request)
        db.commit()
        db.refresh(request)
        return request
    except:
        return


def get_request(db: Session, request_id, user_id):
    return db.query(models.Request).filter(models.Request.id == request_id and models.Request.user == user_id).order_by(
        models.Request.id.desc()).first()


def remove_request(db: Session, request: models.Request):
    try:
        db.delete(request)
        db.commit()
    except:
        return


def get_videos(db: Session, offset: int, limit: int, lang: str = "en"):
    if lang == "en":
        return db.query(models.Videos.id).count(), db.query(
            models.Videos.id,
            models.Videos.preview,
            models.Videos.title_en.label('title'),
            models.Videos.description_en.label('description'),
            models.Videos.link
        ).offset(offset).limit(limit)
    return db.query(models.Videos.id).count(), db.query(
        models.Videos.id,
        models.Videos.preview,
        models.Videos.title_it.label('title'),
        models.Videos.description_it.label('description'),
        models.Videos.link
    ).offset(offset).limit(limit)


def get_questions(db: Session, offset: int, limit: int, lang: str = "en"):
    if lang == "en":
        return db.query(models.FaQ).count(), db.query(
            models.FaQ.id,
            models.FaQ.question_en.label('question')
        ).offset(offset).limit(limit)
    return db.query(models.FaQ).count(), db.query(
        models.FaQ.id,
        models.FaQ.question_it.label('question')
    ).offset(offset).limit(limit)


def get_question_by_id(db: Session, faq_id: int, lang: str = "en"):
    if lang == "en":
        return db.query(
            models.FaQ.id,
            models.FaQ.question_en.label('question'),
            models.FaQ.answer_en.label('answer'),
        ).filter(models.FaQ.id == faq_id).first()
    return db.query(
        models.FaQ.id,
        models.FaQ.question_it.label('question'),
        models.FaQ.answer_it.label('answer'),
    ).filter(models.FaQ.id == faq_id).first()


def _sum_of_digits(x: int):
    result = 0
    for i in str(x):
        result += int(i)
    return result


def get_number(db: Session, date: datetime.datetime, lang: str = "en"):
    number = _sum_of_digits(date.day)
    if lang == "en":
        return db.query(
            models.Numbers.id,
            models.Numbers.number,
            models.Numbers.description_en.label('description'),
        ).filter(models.Numbers.number == number).first()
    return db.query(
        models.Numbers.id,
        models.Numbers.number,
        models.Numbers.description_it.label('description'),
    ).filter(models.Numbers.number == number).first()
