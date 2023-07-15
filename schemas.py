from typing import Optional

from pydantic import BaseModel


class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    country: str

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    email: str
    password: str

    class Config:
        from_attributes = True


class ForgotPasswordRequest(BaseModel):
    email: str

    class Config:
        from_attributes = True


class ForgotPasswordCheckCode(ForgotPasswordRequest):
    code: str


class ForgotPasswordSet(ForgotPasswordRequest):
    password: str
    request_id: str

    class Config:
        from_attributes = True


class CheckCode(ForgotPasswordCheckCode):
    email: str


class UserBase(BaseModel):
    id: str
    name: str
    email: str
    country: str
    avatar: Optional[str] = None
    token: Optional[str] = None

    class Config:
        from_attributes = True


class UserResult(BaseModel):
    id: str
    name: str
    email: str
    country: str
    avatar: Optional[str] = None

    class Config:
        from_attributes = True
