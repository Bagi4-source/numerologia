import hashlib
import random
from sqlalchemy.orm import Session
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
            country=user.country
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
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
    return db.query(models.User).filter(models.User.email == email).first()


def get_user_by_id(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()


def user_remove_tokens(db: Session, user: models.User):
    db.query(models.Token).filter(models.Token.user == user.id).delete()
    db.commit()
    db.refresh(user)


def user_update_password(db: Session, user: models.User, password: str):
    user.password = str(hashed_password(password))
    db.commit()
    db.refresh(user)
    user_remove_tokens(db, user)


def user_update_email(db: Session, user: models.User, email: str):
    user.email = email
    db.commit()
    db.refresh(user)
    user_remove_tokens(db, user)
    return user


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
    return code == str(codeObj.code)


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
