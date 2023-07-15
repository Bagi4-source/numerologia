import datetime
from sqlalchemy import Boolean, DateTime, Column, text, ForeignKey, Integer, String, LargeBinary
from sqlalchemy.dialects.postgresql import UUID
from database import Base
from uuid import uuid4


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, index=True, default=uuid4)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    country = Column(String)
    status = Column(Boolean, default=False)
    created_on = Column(DateTime, default=datetime.datetime.now)
    last_updated = Column(DateTime, onupdate=datetime.datetime.now)


class Token(Base):
    __tablename__ = "token"

    token = Column(UUID(as_uuid=False), primary_key=True, index=True, default=uuid4)
    user = Column(UUID, ForeignKey("users.id", ondelete="cascade"))
    created_on = Column(DateTime, default=datetime.datetime.now)


class Code(Base):
    __tablename__ = "code"

    id = Column(Integer, primary_key=True)
    code = Column(Integer)
    attempts = Column(Integer, default=0)
    step = Column(String)
    user = Column(UUID, ForeignKey("users.id", ondelete="cascade"))
    update_on = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)


class Request(Base):
    __tablename__ = "request"

    id = Column(UUID(as_uuid=False), primary_key=True, index=True, default=uuid4)
    step = Column(String)
    user = Column(UUID, ForeignKey("users.id", ondelete="cascade"))
