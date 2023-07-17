from typing import Optional, List

from pydantic import BaseModel


class UserCreate(BaseModel):
    name: str
    email: str
    password: str

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
    avatar: Optional[str] = None
    token: Optional[str] = None

    class Config:
        from_attributes = True


class ChangeInfo(BaseModel):
    name: str
    email: str

    class Config:
        from_attributes = True


class UserResult(BaseModel):
    id: str
    name: str
    email: str
    avatar: Optional[str] = None

    class Config:
        from_attributes = True


class NumbersBase(BaseModel):
    id: int
    number: int
    description: str

    class Config:
        from_attributes = True


class FaQBase(BaseModel):
    id: int
    question: str

    class Config:
        from_attributes = True


class FaQDetail(FaQBase):
    answer: str


class VideoBase(BaseModel):
    id: int
    preview: str
    title: Optional[str] = None
    description: Optional[str] = None
    link: str

    class Config:
        from_attributes = True


class Videos(BaseModel):
    videos: List[VideoBase]
    count: int
    total: int

    class Config:
        from_attributes = True


class FaQs(BaseModel):
    questions: List[FaQBase]
    count: int
    total: int

    class Config:
        from_attributes = True


class ConfirmCode(BaseModel):
    code: str

    class Config:
        from_attributes = True


class ChangeInfoConfirm(ConfirmCode):
    email: str

    class Config:
        from_attributes = True
