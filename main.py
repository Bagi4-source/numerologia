import datetime
from io import BytesIO
from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException, Form, UploadFile, File
from sqlalchemy.orm import Session
import crud
import models
from router import api_router
import schemas
from database import SessionLocal, engine
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from typing import Annotated
from smtp import send_email
from minioClient import MinioClient
import re
from starlette.requests import Request

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


def password_check(passwd):
    if len(passwd) < 6:
        raise HTTPException(status_code=400, detail="Password length should be at least 6")

    # if not any(char.isdigit() for char in passwd):
    #     print('Password should have at least one numeral')
    #     val = False
    #
    # if not any(char.isupper() for char in passwd):
    #     print('Password should have at least one uppercase letter')
    #     val = False
    #
    # if not any(char.islower() for char in passwd):
    #     print('Password should have at least one lowercase letter')
    #     val = False
    #
    # if not any(char in SpecialSym for char in passwd):
    #     print('Password should have at least one of the symbols $@#')
    #     val = False
    # if val:
    #     return val
    return True


get_bearer_token = HTTPBearer()


@app.post("/signup/", status_code=201, tags=["signup"])
async def signup(
        user: schemas.UserCreate,
        db: Annotated[Session, Depends(get_db)],
):
    if not re.fullmatch(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b', user.email):
        raise HTTPException(status_code=400, detail="Invalid email")

    password_check(user.password)

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
    )
    return {
        'user': result,
        'command': 'check-code'
    }


@app.post("/signup/confirm", status_code=201, tags=["signup"])
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

    src = minio.get_url("avatars", f"{token.user}.png")
    if not src:
        src = minio.get_url("avatars", f"user.png")

    result = schemas.UserBase(
        id=user.id,
        name=user.name,
        email=user.email,
        avatar=src,
        token=token.token
    )
    return result


@app.post("/login/", status_code=201, tags=["signup"])
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

    src = minio.get_url("avatars", f"{token.user}.png")
    if not src:
        src = minio.get_url("avatars", f"user.png")

    result = schemas.UserBase(
        id=db_user.id,
        name=db_user.name,
        email=db_user.email,
        avatar=src,
        token=token.token
    )
    return result


async def check_token(
        auth: Annotated[HTTPAuthorizationCredentials, Depends(get_bearer_token)],
        db: Annotated[Session, Depends(get_db)]
):
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
        token: Annotated[models.Token, Depends(check_token)],
        db: Annotated[Session, Depends(get_db)],
):
    crud.remove_token(db, token)
    return {"status": "ok"}


@app.post("/set-avatar/{user_id}", status_code=200, tags=["signup"])
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
    data = BytesIO()
    data.write(await image.read())
    data.seek(0)

    minio.save_image_bytes("avatars", f"{db_user.id}.png", data, image.size, content_type)
    src = minio.get_url("avatars", f"{db_user.id}.png")
    if not src:
        src = minio.get_url("avatars", f"user.png")

    return {"avatar": src}


@app.post("/change-avatar/", status_code=200, tags=["user_info"])
async def change_avatar(
        token: Annotated[models.Token, Depends(check_token)],
        image: UploadFile
):
    content_type = image.headers.get('content-type')
    if content_type not in ['image/jpeg', 'image/png']:
        raise HTTPException(
            status_code=400,
            detail="Incorrect format",
        )

    data = BytesIO()
    data.write(await image.read())
    data.seek(0)

    minio.save_image_bytes("avatars", f"{token.user}.png", data, image.size, content_type)
    src = minio.get_url("avatars", f"{token.user}.png")
    if not src:
        src = minio.get_url("avatars", f"user.png")

    return {"avatar": src}


@app.get("/get-avatar/", status_code=200, tags=["user_info"])
async def get_avatar(
        token: Annotated[models.Token, Depends(check_token)]
):
    src = minio.get_url("avatars", f"{token.user}.png")
    if not src:
        src = minio.get_url("avatars", f"user.png")

    return {"avatar": src}


@app.get("/get-me/", status_code=200, response_model=schemas.UserResult, tags=["user_info"])
async def get_me(
        token: Annotated[models.Token, Depends(check_token)],
        db: Annotated[Session, Depends(get_db)]
):
    user = crud.get_user_by_id(db=db, user_id=token.user)
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    src = minio.get_url("avatars", f"{token.user}.png")
    if not src:
        src = minio.get_url("avatars", f"user.png")

    result = schemas.UserResult(
        id=user.id,
        name=user.name,
        email=user.email,
        avatar=src
    )

    return result


@app.post("/delete-me/request", status_code=200, tags=["user"])
async def delete_me_request(
        token: Annotated[models.Token, Depends(check_token)],
        db: Annotated[Session, Depends(get_db)]
):
    user = crud.get_user_by_id(db=db, user_id=token.user)
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    codeObj = crud.get_code(db=db, user_id=user.id, step="deleteme")
    if codeObj:
        t = 60 - int(datetime.datetime.now().timestamp() - codeObj.update_on.timestamp())
        if t >= 0:
            raise HTTPException(status_code=429, detail=f"Please wait [{t}] seconds")
        else:
            crud.update_code(db=db, code=codeObj)
    else:
        codeObj = crud.create_code(db=db, user_id=user.id, step="deleteme")
        if not codeObj:
            raise HTTPException(status_code=400, detail="Create code error")

    try:
        send_email([user.email], code=str(codeObj.code), theme="Удаление профиля", text="Удаление профиля")
    except Exception as e:
        print(e)

    return {
        "status": "ok",
        "command": "delete-me-check-code"
    }


@app.post("/delete-me/confirm", status_code=200, tags=["user"])
async def delete_me_confirm(
        o: schemas.ConfirmCode,
        token: Annotated[models.Token, Depends(check_token)],
        db: Annotated[Session, Depends(get_db)]
):
    code = o.code
    user = crud.get_user_by_id(db=db, user_id=token.user)
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    codeObj = crud.get_code(db=db, user_id=user.id, step="deleteme")
    if not codeObj:
        raise HTTPException(status_code=400, detail="Code not found")

    if int(datetime.datetime.now().timestamp() - codeObj.update_on.timestamp()) > 300:
        crud.remove_code(db, codeObj)
        raise HTTPException(status_code=410, detail="Code is outdated")

    verified = crud.verify_code(db=db, codeObj=codeObj, code=code)
    if not verified:
        raise HTTPException(status_code=400, detail="Incorrect code")

    crud.delete_user(db=db, user=user)

    return {
        "status": "ok",
    }


@app.post("/forgot-password/request", status_code=200, tags=["forgot_password"])
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


@app.post("/forgot-password/confirm", status_code=200, tags=["forgot_password"])
async def forgot_password_confirm(
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
        "request_id": request_id,
        "command": "forgot-password-set"
    }


@app.post("/forgot-password/set", status_code=200, tags=["forgot_password"])
async def forgot_password_set(
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
        "status": "ok",
        "command": "login"
    }


@app.post("/change-info/request", status_code=200, tags=["change_info"])
async def change_info_request(
        o: schemas.ChangeInfo,
        token: Annotated[models.Token, Depends(check_token)],
        db: Annotated[Session, Depends(get_db)],
):
    name = o.name.strip()
    email = o.email.strip()
    db_user = crud.get_user_by_id(db=db, user_id=token.user)
    if not db_user:
        raise HTTPException(status_code=400, detail="User not found")

    if email == db_user.email:
        crud.user_update_name(db=db, user=db_user, name=name)
        return {
            "status": "ok",
            "command": "get-me",
        }

    if crud.get_user_by_email(db=db, email=email):
        raise HTTPException(status_code=400, detail="Email already in use")

    codeObj = crud.get_code(db=db, user_id=db_user.id, step="changeemail")
    if codeObj:
        t = 60 - int(datetime.datetime.now().timestamp() - codeObj.update_on.timestamp())
        if t >= 0:
            raise HTTPException(status_code=429, detail=f"Please wait [{t}] seconds")
        else:
            crud.update_code(db=db, code=codeObj)
    else:
        codeObj = crud.create_code(db=db, user_id=db_user.id, step="changeemail")
        if not codeObj:
            raise HTTPException(status_code=400, detail="Create code error")

    try:
        send_email([email], code=str(codeObj.code), theme="Изменение почты", text="Изменение почты")
    except Exception as e:
        print(e)

    return {
        "status": "ok",
        "command": "change-info-confirm"
    }


@app.post("/change-info/confirm", status_code=200, tags=["change_info"])
async def change_info_confirm(
        o: schemas.ChangeInfoConfirm,
        token: Annotated[models.Token, Depends(check_token)],
        db: Annotated[Session, Depends(get_db)],
):
    code = o.code
    email = o.email.strip()

    user = crud.get_user_by_id(db=db, user_id=token.user)
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    codeObj = crud.get_code(db=db, user_id=user.id, step="changeemail")
    if not codeObj:
        raise HTTPException(status_code=400, detail="Code not found")

    if int(datetime.datetime.now().timestamp() - codeObj.update_on.timestamp()) > 300:
        crud.remove_code(db, codeObj)
        raise HTTPException(status_code=410, detail="Code is outdated")

    verified = crud.verify_code(db=db, codeObj=codeObj, code=code)
    if not verified:
        raise HTTPException(status_code=400, detail="Incorrect code")

    crud.user_update_email(db=db, user=user, email=email)

    return {
        "status": "ok",
        "command": "login"
    }


app.include_router(api_router, dependencies=[Depends(check_token)])
