from typing import Optional, List

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


class PublicAccount(AccountBase):
    id: int


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


class CourseMetadata(BaseModel):
    iconUrl: str = ''
    websiteUrl: str = ''
    catalogUrl: str = ''


class RatingAttribute(BaseModel):
    name: str
    description: str


class CourseRatingAttribute(BaseModel):
    id: int
    name: str
    description: str


class CourseRatingAttributeInfo(CourseRatingAttribute):
    usageCount: int


class RatingAttributeIn(RatingAttribute):
    id: str


class SingleCourseRatingIn(BaseModel):
    id: str
    value: int


class CourseRatingIn(BaseModel):
    ratings: List[SingleCourseRatingIn]
    overallRating: int
    description: str
    newRatingAttributes: List[RatingAttributeIn] = []


class RatingAttributeValueInfo(BaseModel):
    attributeID: int
    average: float
    count: int


class SingleRatingInfo(BaseModel):
    attributeID: int
    value: float


class CourseReview(BaseModel):
    account: PublicAccount
    description: str = ''
    date: int
    ratings: List[SingleRatingInfo]


class CourseRatingInfo(BaseModel):
    attributes: List[RatingAttributeValueInfo]
    reviews: List[CourseReview]
