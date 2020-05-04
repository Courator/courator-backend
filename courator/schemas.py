from typing import Optional

from fastapi.params import Query
from pydantic import BaseModel

PERM_ADMIN = 0b10
PERM_USER = 0b01


class Token(BaseModel):
    access_token: str
    token_type: str


###############
# University

class UniversityBase(BaseModel):
    name: str
    code: str
    website: str = ''
    description: str = ''


class UniversityIn(UniversityBase):
    pass


class University(UniversityBase):
    id: int


###############
# Account

class AccountBase(BaseModel):
    name: str = ''
    email: str
    about: str = ''


class AccountIn(AccountBase):
    password: str


class Account(AccountBase):
    id: int
    permissions: int = 0b01


###############
# Course

class CourseBase(BaseModel):
    title: str = ''
    description: str = ''
    website: str = ''
    professorID: Optional[int] = None


class CourseIn(CourseBase):
    code: str = Query(..., max_length=20, regex="^[A-Za-z]+ *[0-9]+$")


class CourseUpdateIn(CourseBase):
    pass


class Course(CourseBase):
    code: str
    universityID: int