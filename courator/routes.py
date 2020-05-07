import asyncio
import base64
import re
from asyncio import ensure_future
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Optional, List
from urllib.parse import urljoin

import httpx
import jwt
from async_lru import alru_cache
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException
from fastapi import status
from fastapi.params import Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jwt import PyJWTError
from loguru import logger
from passlib.context import CryptContext
from pymysql import IntegrityError

from courator import db
from courator.config import TOKEN_EXPIRATION_DAYS, SECRET_KEY, TOKEN_ALGORITHM
from courator.schemas import AccountIn, Account, University, UniversityIn, PERM_ADMIN, Course, CourseIn, CourseUpdateIn, \
    Token, CourseMetadata, CourseRatingIn, SingleCourseRatingIn, CourseRatingAttribute, CourseRatingAttributeInfo, \
    RatingAttribute, CourseRatingInfo, RatingAttributeValueInfo, CourseReview, PublicAccount, SingleRatingInfo

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def auth_account(token: str = Depends(oauth2_scheme)) -> Account:
    account_id = decode_account_token(token)
    if not account_id:
        raise credentials_exception
    fields = Account.__fields__
    query = 'SELECT {} FROM Account WHERE id = :id'.format(', '.join(fields))
    account_data = await db.fetch_one(query, dict(id=account_id))
    if not account_data:
        raise credentials_exception
    return Account(**dict(zip(fields, account_data)))


async def auth_admin_account(token: str = Depends(oauth2_scheme)) -> Account:
    account = await auth_account(token)
    if not account.permissions & PERM_ADMIN:
        raise credentials_exception
    return account


@router.post('/account', response_model=Account)
async def account_create(account: AccountIn):
    password_hash = pwd_context.hash(account.password)
    account_data = dict(**account.dict(exclude={'password'}), passwordHash=password_hash)
    try:
        account_data['id'] = await db.execute(
            'INSERT INTO Account (name, email, passwordHash, about) VALUES (:name, :email, :passwordHash, :about)',
            account_data
        )
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Email already registered')
    return Account(**account_data)


@router.get('/account', response_model=Account)
async def account_get(account: Account = Depends(auth_account)):
    return account


@router.get('/account/{account_id}', response_model=Account)
async def account_get(account_id: str, account: Account = Depends(auth_account)):
    if account.id != account_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail='Not authorized for account')
    return account


def encode_account_token(account_id: int) -> str:
    return jwt.encode({
        'sub': 'account:{}'.format(account_id),
        'exp': datetime.utcnow() + timedelta(days=TOKEN_EXPIRATION_DAYS)
    }, str(SECRET_KEY), algorithm=TOKEN_ALGORITHM)


def decode_account_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, str(SECRET_KEY), algorithms=[TOKEN_ALGORITHM])
    except PyJWTError:
        return None
    auth: str = payload.get("sub")
    if not auth:
        return None
    parts = auth.split(':')
    if len(parts) != 2:
        return None
    auth_type, auth_value = parts
    if auth_type != 'account':
        return None
    try:
        return int(auth_value)
    except ValueError:
        return None


@router.post('/token', response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    query = 'SELECT id, passwordHash FROM Account WHERE email = :email'
    data = await db.fetch_one(query, dict(email=form_data.username))
    if data:
        account_id, password_hash = data
        if pwd_context.verify(form_data.password, password_hash):
            return Token(
                access_token=encode_account_token(account_id),
                token_type="bearer"
            )
    raise HTTPException(status_code=401, detail="Incorrect username or password")


def process_query_filters(args: dict, **where):
    filters = []
    for k, v in list(args.items()):
        if v is None or v == '':
            del args[k]
        else:
            filters.append(where.get(k, '{0} {1} :{0}'.format(
                k, 'LIKE' if isinstance(v, str) else '='
            )))
    return filters


async def get_university_id(university_code: str) -> int:
    query = 'SELECT id FROM University WHERE code = :code'
    data = await db.fetch_one(query, dict(code=university_code))
    if not data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'University not found')
    return data[0]


async def ensure_course_exists(code: str, university_id: int):
    query = 'SELECT code, universityID FROM Course WHERE code = :code AND universityID = :universityID'
    if not await db.fetch_one(query, dict(code=code, universityID=university_id)):
        raise HTTPException(status_code=404, detail='Course not found')


@router.get('/university', response_model=List[University])
async def get_universities(name: str = '', id: int = None, website: str = ''):
    fields = list(University.__fields__)
    args = dict(id=id, name=name, website=website)
    filters = process_query_filters(args, name='(name LIKE :name OR shortName LIKE :name)')
    statements = ['SELECT {} FROM University'.format(', '.join(fields))]
    if filters:
        statements += ['WHERE ' + ' AND '.join(filters)]
    query = ' '.join(statements)
    return [
        University(**dict(zip(fields, row)))
        for row in await db.fetch_all(query, args)
    ]


@router.get('/university/{university_code}', response_model=University)
async def get_university(university_code: str):
    fields = list(University.__fields__)
    query = 'SELECT {} FROM University WHERE code = :code'.format(', '.join(fields))
    row = await db.fetch_one(query, dict(code=university_code))
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'University not found')
    return University(**dict(zip(fields, row)))


@router.post('/university', response_model=University)
async def create_university(university: UniversityIn, account: Account = Depends(auth_account)):
    fields = university.__fields__
    data = university.dict()
    data['id'] = await db.execute(
        'INSERT INTO University ({}) VALUES ({})'.format(
            ', '.join(fields),
            ', '.join(':' + i for i in fields)
        ),
        data
    )
    return University(**data)


@router.put('/university/{university_code}', response_model=University)
async def update_university(university: UniversityIn, university_code: str, account: Account = Depends(auth_account)):
    data = dict(university.dict(), id=await get_university_id(university_code))
    await db.execute(
        'UPDATE University SET {} WHERE id = :id'.format(', '.join(
            '{0} = :{0}'.format(i) for i in university.__fields__
        )),
        data
    )
    return University(**data)


@router.delete('/university/{university_code}', response_model={})
async def delete_university(university_code: str, account: Account = Depends(auth_account)):
    deleted = await db.execute(
        'DELETE FROM University WHERE code = :code',
        dict(code=university_code)
    )
    if deleted != 1:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'University not found')
    return {}


@router.get('/university/{university_code}/course', response_model=List[Course])
async def get_courses(university_code: str, code: str = '', title: str = '', description: str = '', query: str = ''):
    fields = list(Course.__fields__)
    args = dict(
        code=code, title=title, description=description,
        query='%{}%'.format(query) * bool(query), universityID=await get_university_id(university_code)
    )
    filters = process_query_filters(
        args, query='(code LIKE :query OR title LIKE :query)'
    )
    query = 'SELECT {} FROM Course ' \
            'WHERE {}'.format(', '.join(fields), ' AND '.join(filters))
    return [
        Course(**dict(zip(fields, row)))
        for row in await db.fetch_all(query, args)
    ]


def parse_course_code(course_code):
    m = re.match(r'([A-Za-z]+) *([0-9]+)', course_code)
    assert m
    return m.group(1).upper(), m.group(2)


def format_course_code(course_code):
    return '{} {}'.format(*parse_course_code(course_code))


@router.post('/university/{university_code}/course', response_model=Course)
async def create_course(course: CourseIn, university_code: str, account: Account = Depends(auth_account)):
    data = dict(course.dict(), universityID=await get_university_id(university_code))
    dep, num = parse_course_code(data['code'])
    data['departmentCode'] = dep
    data['code'] = dep + num
    await db.execute(
        'INSERT INTO Course ({}) VALUES ({})'.format(
            ', '.join(data),
            ', '.join(':' + i for i in data)
        ),
        data
    )
    return Course(**data)


@router.put('/university/{university_code}/course/{course_code}', response_model=Course)
async def update_course(course: CourseUpdateIn, university_code: str, course_code: str,
                        account: Account = Depends(auth_account)):
    fields = course.__fields__
    data = dict(course.dict(), universityID=await get_university_id(university_code), code=course_code)
    await ensure_course_exists(data['code'], data['universityID'])
    await db.execute(
        'UPDATE Course SET {} WHERE code = :code AND universityID = :universityID'.format(', '.join(
            '{0} = :{0}'.format(i) for i in fields
        )),
        data
    )
    return Course(**data)


@router.delete('/university/{university_code}/course/{course_code}', response_model={})
async def delete_course(university_code: str, course_code: str, account: Account = Depends(auth_account)):
    data = dict(universityID=await get_university_id(university_code), code=course_code)
    await ensure_course_exists(data['code'], data['universityID'])
    await db.execute(
        'DELETE FROM Course WHERE code = :code AND universityID = :universityID',
        data
    )
    return {}


async def get_course(university_code: str, course_code: str):
    fields = list(Course.__fields__)
    args = dict(code=course_code, universityID=await get_university_id(university_code))
    query = 'SELECT {} FROM Course WHERE universityID = :universityID AND code = :code'.format(', '.join(fields))
    row = await db.fetch_one(query, args)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Course not found')
    return Course(**dict(zip(fields, row)))


@router.get('/university/{university_code}/course/{course_code}', response_model=Course)
async def get_course_route(university_code: str, course_code: str):
    return await get_course(university_code, course_code)


async def guess_url(query, client: httpx.AsyncClient):
    r = await client.get('https://www.google.com/search?btnI=&q=', params={'btnI': '', 'q': query},
                         allow_redirects=False)
    if r.is_redirect and 'location' in r.headers:
        website = r.headers['location']
        prefix = 'https://www.google.com/url?q='
        if website.startswith(prefix):
            website = website[len(prefix):]
        return website
    return ''


def generate_data_url(r):
    content_type = r.headers["content-type"]
    data_string = base64.b64encode(r.content).decode()
    data_url = "data:{};base64,{}".format(content_type, data_string)
    return data_url


def guc_icon_favicon_request_args(url: str) -> dict:
    return dict(url='https://s2.googleusercontent.com/s2/favicons', params={'domain_url': url})


@lru_cache(1)
def guc_get_generic_icon_data() -> str:
    return generate_data_url(httpx.get(**guc_icon_favicon_request_args('.')))


async def get_favicon_data(website, client) -> str:
    website_cor = client.get(website)
    guc_cor = asyncio.ensure_future(client.get(**guc_icon_favicon_request_args(website)))
    bs = BeautifulSoup((await website_cor).text, 'html.parser')
    link = bs.find("link", rel=lambda x: 'icon' in x.split())
    if link:
        guc_cor.cancel()
        return generate_data_url(await client.get(urljoin(website, link['href'])))
    guc_icon_url = generate_data_url(await guc_cor)
    if guc_icon_url != guc_get_generic_icon_data():
        return guc_icon_url
    return ''


async def replace_error(coroutine, error_type, value):
    try:
        return await coroutine
    except error_type as e:
        logger.debug('Error running coroutine: {}', e)
        return value


@router.get('/university/{university_code}/course/{course_code}/metadata', response_model=CourseMetadata)
@alru_cache(maxsize=30)
async def get_course_metadata(university_code: str, course_code: str):
    course_cor = ensure_future(db.fetch_one(
        'SELECT 1 FROM Course c JOIN University u ON c.universityID = u.id WHERE u.code = :ucode AND c.code = :ccode',
        dict(ucode=university_code, ccode=course_code)))
    metadata = CourseMetadata()
    async with httpx.AsyncClient() as client:
        code = format_course_code(course_code)
        website_cors = [
            ensure_future(guess_url(fmt.format(univ=university_code, course=code), client))
            for fmt in
            ['{univ} {course} home page', '{univ} {course} page', '{univ} {course} homepage', '{univ} {course} website']
        ]
        info_cor = ensure_future(guess_url('{} course description {}'.format(code, university_code), client))

        metadata.catalogUrl = await replace_error(info_cor, httpx.HTTPError, '')

        for website_cor in website_cors:
            website = await replace_error(website_cor, httpx.HTTPError, '')
            if website and website != metadata.catalogUrl:
                metadata.websiteUrl = website
                break

        if metadata.websiteUrl:
            metadata.iconUrl = await replace_error(get_favicon_data(website, client), httpx.HTTPError, '')

    if not await course_cor:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'No such course/university')

    return metadata


@router.post('/university/{university_code}/course/{course_code}/rating', response_model={})
async def submit_rating(university_code: str, course_code: str, course_rating: CourseRatingIn,
                        account: Account = Depends(auth_account)):
    id_to_dbid = {}
    course = await get_course(university_code, course_code)
    if await db.fetch_one('SELECT * FROM CourseRating WHERE accountID = :accountID AND courseCode = :courseCode AND universityID = :universityID', dict(accountID=account.id, courseCode=course_code, universityID=course.universityID)):
        raise HTTPException(status.HTTP_409_CONFLICT, 'Already rated class')
    for new_attr in course_rating.newRatingAttributes:
        new_id = await db.execute(
            'INSERT INTO CourseRatingAttribute(name, description) VALUES (:name, :description)',
            dict(name=new_attr.name, description=new_attr.description)
        )
        id_to_dbid[new_attr.id] = new_id
    r = await db.fetch_one('SELECT id FROM CourseRatingAttribute WHERE name = :name', dict(name='_Overall'))
    if not r:
        overall_id = await db.execute(
            'INSERT INTO CourseRatingAttribute(name, description) VALUES (:name, :description)',
            dict(name='.overall', description='Overall course rating')
        )
    else:
        overall_id = r[0]
    date_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    rating_id = await db.execute(
        'INSERT INTO CourseRating(description, date, accountID, courseCode, universityID) VALUES '
        '(:description, :date, :accountID, :courseCode, :universityID)',
        dict(
            description=course_rating.description, date=date_str, accountID=account.id, courseCode=course.code,
            universityID=course.universityID
        )
    )
    try:
        for rating in course_rating.ratings + [
            SingleCourseRatingIn(id=str(overall_id), value=course_rating.overallRating)
        ]:
            real_id = id_to_dbid.get(rating.id)
            if not real_id:
                real_id = int(rating.id)
            await db.execute(
                'INSERT INTO CourseRatingValue(courseRatingID, courseRatingAttributeID, value) VALUES '
                '(:ratingID, :attributeID, :value)',
                dict(
                    ratingID=rating_id, attributeID=real_id, value=rating.value / 5.0
                )
            )
    except (ValueError, IntegrityError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail='Invalid rating id')

    return {}


@router.get('/university/{university_code}/course/{course_code}/rating', response_model=CourseRatingInfo)
async def get_ratings(university_code: str, course_code: str):
    course = await get_course(university_code, course_code)
    attribute_ratings = await db.fetch_all(
        'SELECT attributeID, attributeCount, avgRating '
        'FROM (' + (
            'SELECT crv.courseRatingAttributeID AS attributeID, COUNT(crv.value) AS attributeCount, AVG(crv.value) AS avgRating '
            'FROM CourseRatingValue crv '
            'INNER JOIN CourseRating cr ON cr.id = crv.courseRatingID '
            'WHERE cr.courseCode = :courseCode AND cr.universityID = :universityID '
            'GROUP BY crv.courseRatingAttributeID'
        ) + ') s ' +
        'ORDER BY attributeCount',
        dict(courseCode=course.code, universityID=course.universityID)
    )
    reviews = await db.fetch_all(
        'SELECT a.name AS accountName, a.email AS accountEmail, a.about AS accountAbout, '
        '   a.id AS accountID, cr.description AS description, cr.date AS date, '
        '   GROUP_CONCAT(crv.value SEPARATOR \',\') AS ratings, '
        '    GROUP_CONCAT(cra.id SEPARATOR \',\') AS ratingIDs '
        'FROM CourseRating cr '
        'INNER JOIN Account a ON a.id = cr.accountID '
        'INNER JOIN CourseRatingValue crv ON crv.courseRatingID = cr.id '
        'INNER JOIN CourseRatingAttribute cra ON cra.id = crv.courseRatingAttributeID '
        'WHERE cr.courseCode = :courseCode AND cr.universityID = :universityID '
        'GROUP BY cr.id '
        'ORDER BY cr.date',
        dict(courseCode=course_code, universityID=course.universityID)
    )
    print('REVIEW:', reviews)
    return CourseRatingInfo(
        attributes=[
            RatingAttributeValueInfo(attributeID=attribute_id, average=avg_rating, count=attribute_count)
            for attribute_id, attribute_count, avg_rating in attribute_ratings
        ],
        reviews=[
            CourseReview(account=PublicAccount(name=accountName, id=accountID, email=accountEmail, about=accountAbout), description=description, date=date.timestamp(), ratings=[
                SingleRatingInfo(value=float(val), attributeID=int(ratingID))
                for val, ratingID in zip(ratings.split(','), ratingIDs.split(','))
            ])
            for accountName, accountEmail, accountAbout, accountID, description, date, ratings, ratingIDs in reviews
            if accountName is not None
        ]
    )


@router.get('/ratingAttribute', response_model=List[CourseRatingAttribute])
async def get_rating_attributes(count: Optional[int] = None):
    rows = await db.fetch_all('SELECT SUM(1) AS attributeCount, cra.id, name, description '
                              'FROM CourseRatingValue crv '
                              'RIGHT JOIN CourseRatingAttribute cra ON cra.id = crv.courseRatingAttributeID '
                              'GROUP BY cra.id ORDER BY attributeCount DESC' + (
                                  ' LIMIT :count' if count is not None else ''),
                              dict(count=count) if count is not None else {})
    return [
        CourseRatingAttributeInfo(id=attribute_id, name=name, description=description, usageCount=usage_count)
        for usage_count, attribute_id, name, description in rows
    ]


@router.post('/ratingAttribute', response_model=CourseRatingAttribute)
async def post_rating_attribute(rating_attribute: RatingAttribute, account: Account = Depends(auth_account)):
    rating_attribute_id = await db.execute(
        'INSERT INTO CourseRatingAttribute(name, description) VALUES (:name, :description)',
        dict(name=rating_attribute.name, description=rating_attribute.description)
    )
    return CourseRatingAttribute(id=rating_attribute_id, **rating_attribute.dict())
