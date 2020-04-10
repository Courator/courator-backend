import os

import pymysql
from flask import Flask
from flask_restplus import Api
from flask_database import Database

app = Flask(__name__)
db = Database(
    app,
    pymysql,
    host='127.0.0.1',
    port=3306,
    user='courator',
    password='courator123',
    database='courator'
)
api = Api(app, ui=False)

import courator.routes  # noqa
