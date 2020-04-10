from courator import db

schemas = [
    ('''CREATE TABLE University(
        id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(80) NOT NULL,
        shortName VARCHAR(20) NOT NULL UNIQUE,
        website VARCHAR(80)
    )''', 'University'),
    ('''CREATE TABLE Course(
        id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
        shortName VARCHAR(16) NOT NULL,
        name VARCHAR(40) NOT NULL,
        description VARCHAR(1000),
        departmentCode VARCHAR(8) NOT NULL,
        professorID INTEGER REFERENCES Professor,
        universityID INTEGER NOT NULL REFERENCES University
    )''', 'Course'),
    ('''CREATE TABLE Professor(
        id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(40) NOT NULL,
        email VARCHAR(60) UNIQUE,
        universityID INTEGER NOT NULL REFERENCES University
    )''', 'Professor'),
    ('''CREATE TABLE TA(
        id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(40),
        email VARCHAR(60) UNIQUE,
        universityID INTEGER NOT NULL REFERENCES University
    )''', 'TA'),
    ('''CREATE TABLE Account(
        id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(40),
        email VARCHAR(60) NOT NULL UNIQUE,
        passwordHash VARCHAR(120) NOT NULL,
        about VARCHAR(512)
    )''', 'Account'),

    ('''CREATE TABLE CourseRating(
        id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
        description VARCHAR(1000),
        date DATE NOT NULL,
        accountID INTEGER NOT NULL REFERENCES Account,
        courseID INTEGER NOT NULL REFERENCES Course
    )''', 'CourseRating'),
    ('''CREATE TABLE CourseRatingAttribute(
        id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(40) NOT NULL,
        description VARCHAR(200)
    )''', 'CourseRatingAttribute'),
    ('''CREATE TABLE CourseRatingValue(
        id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
        courseRatingID INTEGER NOT NULL REFERENCES CourseRating,
        courseRatingAttributeID INTEGER NOT NULL REFERENCES CourseRatingAttribute,
        value DOUBLE NOT NULL
    )''', 'CourseRatingValue'),

    ('''CREATE TABLE ProfessorRating(
        id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
        description VARCHAR(1000),
        date DATE,
        accountID INTEGER NOT NULL REFERENCES Account,
        professorID INTEGER NOT NULL REFERENCES Professor
    )''', 'ProfessorRating'),
    ('''CREATE TABLE ProfessorRatingAttribute(
        id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(40) NOT NULL,
        description VARCHAR(200)
    )''', 'ProfessorRatingAttribute'),
    ('''CREATE TABLE ProfessorRatingValue(
        id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
        professorRatingID INTEGER NOT NULL REFERENCES ProfessorRating,
        professorRatingAttributeID INTEGER NOT NULL REFERENCES ProfessorRatingAttribute,
        value DOUBLE NOT NULL
    )''', 'ProfessorRatingValue'),

    ('''CREATE TABLE TARating(
        id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
        description VARCHAR(1000),
        date DATE,
        accountID INTEGER NOT NULL REFERENCES Account,
        taID INTEGER NOT NULL REFERENCES TA
    )''', 'TARating'),
    ('''CREATE TABLE TARatingAttribute(
        id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(40) NOT NULL,
        description VARCHAR(200)
    )''', 'TARatingAttribute'),
    ('''CREATE TABLE TARatingValue(
        id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
        taRatingID INTEGER NOT NULL REFERENCES TARating,
        taRatingAttributeID INTEGER NOT NULL REFERENCES TARatingAttribute,
        value DOUBLE NOT NULL
    )''', 'TARatingValue'),

    ('''CREATE TABLE Prerequisite(
        prereqID INTEGER NOT NULL REFERENCES Course,
        courseID INTEGER NOT NULL REFERENCES Course,
        PRIMARY KEY(prereqID, courseID)
    )''', 'Prerequisite'),
    ('''CREATE TABLE TACourse(
        taID INTEGER NOT NULL REFERENCES TA,
        courseID INTEGER NOT NULL REFERENCES Course,
        PRIMARY KEY(taID, courseID)
    )''', 'TACourse')
]


def init_db():
    db.detach()
    for table_str, table_name in schemas:
        print('Creating "{}"...'.format(table_name))
        db.run(table_str)


def delete_db():
    db.detach()
    for _, table_name in schemas:
        print('Deleting "{}"...'.format(table_name))
        db.run('DROP TABLE IF EXISTS {}'.format(table_name))
