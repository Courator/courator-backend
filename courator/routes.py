import re
from contextlib import contextmanager
from datetime import datetime

from flask import request
from flask_restx import Resource
from passlib.hash import pbkdf2_sha256
from pymysql import IntegrityError
from pymysql.err import MySQLError
from werkzeug.exceptions import BadRequest, Conflict

from courator import api, db


@contextmanager
def handle_sql_errors():
    try:
        yield
    except IntegrityError as e:
        message = e.args[1]
        m = re.match(r"Duplicate entry '(?P<value>[^']+)' for key '(?P<key>[^']+)'", message)
        if m:
            raise Conflict('Conflict on column "{}"'.format(m.groupdict()['key']))
        raise BadRequest(message)
    except MySQLError as e:
        raise BadRequest(e.args[1])


db.error_wrapper = handle_sql_errors


class SimpleResource(Resource):
    columns = ()
    optional = set()
    table = ''

    def post(self):
        data = request.json
        try:
            values = tuple(
                data.pop(key, None) if key in self.optional else data.pop(key)
                for key in self.columns
            )
        except KeyError as e:
            raise BadRequest('Missing required attribute: {}'.format(e))

        if data:
            raise BadRequest('Extra data in request: {}'.format(data))
        with handle_sql_errors():
            value_id = db.run('INSERT INTO {} ({}) VALUES ({})'.format(
                self.table,
                ', '.join(self.columns),
                ', '.join(['%s'] * len(self.columns))
            ), values)
        return dict(zip(self.columns, values), id=value_id)

    def get(self):
        columns = ('id',) + self.columns
        data = db.fetch_all('SELECT {} FROM {}'.format(
            ', '.join(columns), self.table
        ))
        return [dict(zip(columns, row)) for row in data]


@api.route('/university')
class University(SimpleResource):
    columns = ('name', 'shortName', 'website')
    optional = {'website'}
    table = 'University'


@api.route('/university/<short_name>')
class UniversityRes(Resource):
    def patch(self, short_name):
        data = request.json
        try:
            update_attributes = [i for i in ('name', 'shortName', 'website') if data.get(i, '')]
            db.run(
                'UPDATE University SET {} WHERE shortName = %s'.format(
                    ', '.join('{} = %s'.format(attr) for attr in update_attributes)
                ), tuple(data[attr] for attr in update_attributes) + (short_name,)
            )
        except KeyError as e:
            raise BadRequest('Missing attribute: {}'.format(e))
        return {'status': 'success'}

    def delete(self, short_name):
        db.run('DELETE FROM University WHERE shortName = %s', (short_name,))
        return {}


@api.route('/professor')
class Professor(SimpleResource):
    columns = ('name', 'email', 'universityID')
    optional = {'email'}
    table = 'Professor'


@api.route('/ta')
class Ta(SimpleResource):
    columns = ('name', 'email', 'universityID')
    table = 'TA'


@api.route('/course')
class Course(SimpleResource):
    columns = ('shortName', 'name', 'departmentCode',
               'professorID', 'universityID')
    table = 'Course'


@api.route('/courseRatingAttribute')
class CourseRatingAttribute(SimpleResource):
    columns = ('name', 'description')
    table = 'CourseRatingAttribute'


@api.route('/account')
class Account(Resource):
    def post(self):
        data = request.json
        try:
            name = data.pop('name', '')
            email = data.pop('email')
            password = data.pop('password')
        except KeyError as e:
            raise BadRequest('Missing required json attribute: {}'.format(e))

        if data:
            raise BadRequest('Extra json data: {}'.format(data))

        password_hash = pbkdf2_sha256.hash(password, rounds=1024)
        account_id = db.run(
            'INSERT INTO Account (name, email, passwordHash, about) VALUES (%s, %s, %s, %s)',
            (name, email, password_hash, 'NULL')
        )
        return {
            'id': account_id,
            'name': name,
            'email': email,
            'about': None
        }

    def get(self):
        try:
            email = request.args['email']
        except KeyError as e:
            raise BadRequest('Missing required json attribute: {}'.format(e))
        columns = ('id', 'name', 'name', 'email', 'about')
        data = db.fetch_one('SELECT {} FROM Account WHERE email = %s'.format(
            ', '.join(columns)), email)
        return dict(zip(data, columns))


@api.route('/courseRating')
class CourseRating(Resource):
    def post(self):
        data = request.json
        try:
            description = data.pop('description', None)
            account_id = data.pop('accountID')
            course_id = data.pop('courseID')
            course_ratings = data.pop('ratings')
        except KeyError as e:
            raise BadRequest('Missing required json attribute: {}'.format(e))

        if data:
            raise BadRequest('Extra json data: {}'.format(data))

        cur_date = datetime.now().strftime('%Y-%m-%d')

        for rating in course_ratings:
            if not set(rating) == {'attributeID', 'value'} or not (0.0 <= float(rating['value']) <= 1.0):
                raise BadRequest('Malformed course rating: {}'.format(rating))

        with db as cursor:
            cursor.execute(
                'INSERT INTO CourseRating (description, date, accountID, courseID) VALUES (%s, %s, %s, %s)',
                (description, cur_date, account_id, course_id)
            )
            rating_id = cursor.lastrowid
            cursor.executemany(
                'INSERT INTO CourseRatingValue (courseRatingID, courseRatingAttributeID, value) VALUES (%s, %s, %s)', [
                    (rating_id, rating['courseRatingAttributeID'],
                     float(rating['value']))
                ])
        return {
            'description': description,
            'accountID': account_id,
            'courseID': course_id,
            'ratings': course_ratings
        }

    def get(self):
        course_id = request.args['course_id']
        rows = db.fetch_all(
            'SELECT AVG(value) AS rating, cra.name AS ratingType, cra.id AS ratingTypeID '
            'FROM CourseRatingValue crv '
            'JOIN CourseRating cr ON cr.id = crv.courseRatingID '
            'JOIN CourseRatingAttribute cra ON cra.id = crv.courseRatingAttributeID '
            'GROUP BY cra.id '
            'WHERE cr.courseID = %s ',
            course_id
        )
        return [
            dict(zip(row, ('rating', 'ratingType', 'ratingTypeID')))
            for row in rows
        ]
