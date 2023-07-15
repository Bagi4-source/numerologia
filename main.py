import datetime
from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException, Form, UploadFile, File
from sqlalchemy.orm import Session
import crud
import models
import schemas
from database import SessionLocal, engine
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from typing import Annotated
from smtp import send_email
from minioClient import MinioClient

minio = MinioClient()

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


get_bearer_token = HTTPBearer()


@app.post("/signup/", status_code=201)
async def signup(
        user: schemas.UserCreate,
        db: Annotated[Session, Depends(get_db)],
):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user and db_user.status:
        raise HTTPException(status_code=400, detail="Email already registered")

    if not db_user:
        db_user = crud.create_user(db=db, user=user)
        if not db_user:
            raise HTTPException(status_code=500, detail="Create user error")

    codeObj = crud.get_code(db=db, user_id=db_user.id, step="signup")
    if codeObj:
        t = 60 - int(datetime.datetime.now().timestamp() - codeObj.update_on.timestamp())
        if t >= 0:
            raise HTTPException(status_code=429, detail=f"Please wait [{t}] seconds")
        else:
            crud.update_code(db=db, code=codeObj)
    else:
        codeObj = crud.create_code(db=db, user_id=db_user.id, step="signup")
        if not codeObj:
            raise HTTPException(status_code=400, detail="Create code error")

    try:
        send_email([db_user.email], code=str(codeObj.code))
    except:
        pass

    result = schemas.UserBase(
        id=db_user.id,
        name=db_user.name,
        email=db_user.email,
        country=db_user.country
    )
    return {
        'user': result,
        'command': 'check-code'
    }


@app.post("/signup/confirm", status_code=201)
async def check_code(
        o: schemas.CheckCode,
        db: Annotated[Session, Depends(get_db)],
):
    email = o.email
    code = o.code

    user = crud.get_user_by_email(db=db, email=email)
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    codeObj = crud.get_code(db=db, user_id=user.id, step="signup")
    if not codeObj:
        raise HTTPException(status_code=400, detail="Code not found")

    if int(datetime.datetime.now().timestamp() - codeObj.update_on.timestamp()) > 300:
        crud.remove_code(db, codeObj)
        raise HTTPException(status_code=410, detail="Code is outdated")

    verified = crud.verify_code(db=db, codeObj=codeObj, code=code)
    if not verified:
        raise HTTPException(status_code=400, detail="Incorrect code")

    user.status = True
    db.commit()
    db.refresh(user)

    token = crud.create_token(db=db, user_id=user.id)
    if not token:
        raise HTTPException(status_code=500, detail="Create token error")

    result = schemas.UserBase(
        id=user.id,
        name=user.name,
        email=user.email,
        country=user.country,
        token=token.token
    )
    return result


@app.post("/login/", status_code=201)
async def login(
        user: schemas.UserLogin,
        db: Annotated[Session, Depends(get_db)],
):
    db_user = crud.get_user_by_email(db, email=user.email)
    if not db_user:
        raise HTTPException(status_code=400, detail="User not found")

    login = crud.verify_password(user=db_user, password=user.password)
    if not login:
        raise HTTPException(status_code=400, detail="Incorrect password")

    token = crud.create_token(db, db_user.id)
    if not token:
        raise HTTPException(status_code=500, detail="Create token error")

    result = schemas.UserBase(
        id=db_user.id,
        name=db_user.name,
        email=db_user.email,
        country=db_user.country,
        token=token.token
    )
    return result


async def check_token(db, auth):
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
        )
    token = crud.get_token(db, auth.credentials)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
        )
    return token


@app.post("/logout/")
async def logout(
        auth: Annotated[HTTPAuthorizationCredentials, Depends(get_bearer_token)],
        db: Annotated[Session, Depends(get_db)],
):
    token = await check_token(db, auth)
    crud.remove_token(db, token)
    return {"status": "ok"}


@app.post("/set-avatar/{user_id}", status_code=200)
async def set_avatar(
        db: Annotated[Session, Depends(get_db)],
        user_id: str,
        image: UploadFile
):
    db_user = crud.get_user_by_id(db, user_id=user_id)
    if not db_user:
        raise HTTPException(status_code=400, detail="User not found")

    if db_user.status:
        raise HTTPException(status_code=400, detail="User already activated")

    content_type = image.headers.get('content-type')
    if content_type not in ['image/jpeg', 'image/png']:
        raise HTTPException(
            status_code=400,
            detail="Incorrect format",
        )

    minio.save_image_bytes("avatars", f"{db_user.id}.png", await image.read(), image.size, content_type)
    url = minio.get_url("avatars", f"{db_user.id}.png")

    return {"image": url}


@app.post("/change-avatar/", status_code=200)
async def change_avatar(
        auth: Annotated[HTTPAuthorizationCredentials, Depends(get_bearer_token)],
        db: Annotated[Session, Depends(get_db)],
        image: UploadFile
):
    token = await check_token(db, auth)

    content_type = image.headers.get('content-type')
    if content_type not in ['image/jpeg', 'image/png']:
        raise HTTPException(
            status_code=400,
            detail="Incorrect format",
        )

    minio.save_image_bytes("avatars", f"{token.user}.png", await image.read(), image.size, content_type)
    url = minio.get_url("avatars", f"{token.user}.png")

    return {"image": url}


@app.get("/get-avatar/", status_code=200)
async def get_avatar(
        auth: Annotated[HTTPAuthorizationCredentials, Depends(get_bearer_token)],
        db: Annotated[Session, Depends(get_db)],
):
    token = await check_token(db, auth)

    url = minio.get_url("avatars", f"{token.user}.png")

    return {"image": url}


@app.get("/user/{user_id}", status_code=200, response_model=schemas.UserBase)
async def get_user(
        auth: Annotated[HTTPAuthorizationCredentials, Depends(get_bearer_token)],
        db: Annotated[Session, Depends(get_db)],
        user_id: str
):
    token = await check_token(db, auth)

    user = crud.get_user_by_id(db=db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    return user


@app.post("/forgot-password/request", status_code=200)
async def forgot_password_request(
        o: schemas.ForgotPasswordRequest,
        db: Annotated[Session, Depends(get_db)],
):
    email = o.email
    db_user = crud.get_user_by_email(db=db, email=email)
    if not db_user:
        raise HTTPException(status_code=400, detail="User not found")

    codeObj = crud.get_code(db=db, user_id=db_user.id, step="forgot")
    if codeObj:
        t = 60 - int(datetime.datetime.now().timestamp() - codeObj.update_on.timestamp())
        if t >= 0:
            raise HTTPException(status_code=429, detail=f"Please wait [{t}] seconds")
        else:
            crud.update_code(db=db, code=codeObj)
    else:
        codeObj = crud.create_code(db=db, user_id=db_user.id, step="forgot")
        if not codeObj:
            raise HTTPException(status_code=400, detail="Create code error")

    try:
        send_email([db_user.email], code=str(codeObj.code), theme="Сброс пароля", text="Сброс пароля")
    except Exception as e:
        print(e)

    return {
        "status": "ok",
        "command": "forgot-check-code"
    }


@app.post("/forgot-password/confirm", status_code=200)
async def forgot_password_request(
        o: schemas.ForgotPasswordCheckCode,
        db: Annotated[Session, Depends(get_db)],
):
    code = o.code
    email = o.email

    db_user = crud.get_user_by_email(db=db, email=email)
    if not db_user:
        raise HTTPException(status_code=400, detail="User not found")

    codeObj = crud.get_code(db=db, user_id=db_user.id, step="forgot")
    if not codeObj:
        raise HTTPException(status_code=400, detail="Code not found")

    if int(datetime.datetime.now().timestamp() - codeObj.update_on.timestamp()) > 300:
        crud.remove_code(db, codeObj)
        raise HTTPException(status_code=410, detail="Code is outdated")

    verified = crud.verify_code(db=db, codeObj=codeObj, code=code)
    if not verified:
        raise HTTPException(status_code=400, detail="Incorrect code")

    request = crud.create_request(db=db, step="forgot", user_id=db_user.id)
    if not request:
        raise HTTPException(status_code=400, detail="Create request error")

    request_id = request.id

    return {
        "status": "ok",
        "request_id": request_id,
        "command": "forgot-check-code"
    }


@app.post("/forgot-password/set", status_code=200)
async def forgot_password_request(
        o: schemas.ForgotPasswordSet,
        db: Annotated[Session, Depends(get_db)],
):
    password = o.password
    request_id = o.request_id
    email = o.email

    db_user = crud.get_user_by_email(db=db, email=email)
    if not db_user:
        raise HTTPException(status_code=400, detail="User not found")

    request = crud.get_request(db=db, request_id=request_id, user_id=db_user.id)
    if not request:
        raise HTTPException(status_code=400, detail="Request not found")
    crud.remove_request(db=db, request=request)

    crud.user_update_password(db=db, user=db_user, password=password)

    return {
        "status": "ok"
    }
