from enum import Enum

from syncer import sync

from . import db


class Obj(Enum):
    table = 1
    index = 2
    function = 3


schemas = [
    ('''CREATE TABLE University(
        id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
        code VARCHAR(20) NOT NULL UNIQUE,
        name VARCHAR(80) NOT NULL,
        description VARCHAR(2000) NOT NULL,
        website VARCHAR(80)
    )''', 'University', Obj.table),
    ('''CREATE TABLE Course(
        universityID INTEGER NOT NULL REFERENCES University,
        code VARCHAR(16) NOT NULL,
        
        title VARCHAR(120) NOT NULL,
        description VARCHAR(2000) NOT NULL,
        website VARCHAR(120) NOT NULL,
        departmentCode VARCHAR(8) NOT NULL,
        professorID INTEGER REFERENCES Professor,
        
        PRIMARY KEY (universityID, code)
    )''', 'Course', Obj.table),
    ('''CREATE TABLE Professor(
        id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(40) NOT NULL,
        email VARCHAR(60) UNIQUE,
        universityID INTEGER NOT NULL REFERENCES University
    )''', 'Professor', Obj.table),
    ('''CREATE TABLE TA(
        id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(40) NOT NULL,
        email VARCHAR(60) UNIQUE,
        universityID INTEGER NOT NULL REFERENCES University
    )''', 'TA', Obj.table),
    ('''CREATE TABLE Account(
        id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(40) NOT NULL,
        email VARCHAR(60) NOT NULL UNIQUE,
        passwordHash VARCHAR(120) NOT NULL,
        about VARCHAR(512) NOT NULL,
        permissions INT NOT NULL DEFAULT 0b01
    )''', 'Account', Obj.table),

    ('''CREATE TABLE CourseRating(
        id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
        description VARCHAR(2000) NOT NULL,
        date DATETIME NOT NULL,
        accountID INTEGER NOT NULL REFERENCES Account,
        universityID INTEGER NOT NULL REFERENCES University,
        courseCode VARCHAR(16) NOT NULL
    )''', 'CourseRating', Obj.table),
    ('''CREATE TABLE CourseRatingAttribute(
        id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(40) NOT NULL,
        description VARCHAR(200)
    )''', 'CourseRatingAttribute', Obj.table),
    ('''CREATE TABLE CourseRatingValue(
        id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
        courseRatingID INTEGER NOT NULL REFERENCES CourseRating,
        courseRatingAttributeID INTEGER NOT NULL REFERENCES CourseRatingAttribute,
        value DOUBLE NOT NULL
    )''', 'CourseRatingValue', Obj.table),

    ('''CREATE TABLE ProfessorRating(
        id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
        description VARCHAR(2000) NOT NULL,
        date DATE,
        accountID INTEGER NOT NULL REFERENCES Account,
        professorID INTEGER NOT NULL REFERENCES Professor
    )''', 'ProfessorRating', Obj.table),
    ('''CREATE TABLE ProfessorRatingAttribute(
        id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(40) NOT NULL,
        description VARCHAR(200)
    )''', 'ProfessorRatingAttribute', Obj.table),
    ('''CREATE TABLE ProfessorRatingValue(
        id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
        professorRatingID INTEGER NOT NULL REFERENCES ProfessorRating,
        professorRatingAttributeID INTEGER NOT NULL REFERENCES ProfessorRatingAttribute,
        value DOUBLE NOT NULL
    )''', 'ProfessorRatingValue', Obj.table),

    ('''CREATE TABLE TARating(
        id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
        description VARCHAR(2000) NOT NULL,
        date DATE,
        accountID INTEGER NOT NULL REFERENCES Account,
        taID INTEGER NOT NULL REFERENCES TA
    )''', 'TARating', Obj.table),
    ('''CREATE TABLE TARatingAttribute(
        id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(40) NOT NULL,
        description VARCHAR(200)
    )''', 'TARatingAttribute', Obj.table),
    ('''CREATE TABLE TARatingValue(
        id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
        taRatingID INTEGER NOT NULL REFERENCES TARating,
        taRatingAttributeID INTEGER NOT NULL REFERENCES TARatingAttribute,
        value DOUBLE NOT NULL
    )''', 'TARatingValue', Obj.table),

    ('''CREATE TABLE Prerequisite(
        prereqID INTEGER NOT NULL REFERENCES Course,
        courseID INTEGER NOT NULL REFERENCES Course,
        PRIMARY KEY(prereqID, courseID)
    )''', 'Prerequisite', Obj.table),
    ('''CREATE TABLE TACourse(
        taID INTEGER NOT NULL REFERENCES TA,
        courseID INTEGER NOT NULL REFERENCES Course,
        PRIMARY KEY(taID, courseID)
    )''', 'TACourse', Obj.table),
    ('''DROP PROCEDURE IF EXISTS compute_correlation;
DELIMITER ;;
CREATE PROCEDURE compute_correlation(input_account_id INTEGER)
BEGIN
    WITH RValues AS (
        SELECT crv.courseRatingAttributeID AS attrID, crv.value AS value, cr.id AS rID
        FROM CourseRating cr
        JOIN CourseRatingValue crv ON crv.courseRatingID = cr.id
        WHERE cr.accountID = input_account_id
    ),
    Averages AS (
        SELECT attrID, AVG(value) AS meanValue
        FROM RValues
        GROUP BY attrID
    ),
    Centered AS (
        SELECT v.attrID AS attrID, (value - av.meanValue) AS centeredValue, rID
        FROM RValues v
        JOIN Averages av ON av.attrID = v.attrID
    ),
    Variances AS (
        SELECT attrID, AVG(centeredValue * centeredValue) AS varValue
        FROM Centered
        GROUP BY attrID
    ),
    Normalized AS (
        SELECT c.attrID AS attrID, centeredValue / SQRT(varValue) AS normValue, rID
        FROM Centered c
        JOIN Variances var ON var.attrID = c.attrID
    ),
    OverallValues AS (
        SELECT r.attrID AS attrID, r.rID AS rID, r.value AS overallValue
        FROM RValues r
        JOIN CourseRatingAttribute cra ON cra.id = r.attrID
        WHERE cra.name = '_Overall'
    ),
    OverallMean AS (SELECT AVG(overallValue) FROM OverallValues),
    OverallCentered AS (
        SELECT v.attrID AS attrID, (overallValue - (SELECT * FROM OverallMean)) AS overallCenteredValue, rID
        FROM OverallValues v
    ),
    OverallVariance AS (
        SELECT AVG(overallCenteredValue * overallCenteredValue) AS overallVarianceValue
        FROM OverallCentered
    ),
    OverallNorm AS (
        SELECT c.attrID AS attrID, overallCenteredValue / SQRT(var.overallVarianceValue) AS overallNormValue, rID
        FROM OverallCentered c
        JOIN OverallVariance var ON TRUE
    ),
    Correlation AS (
        SELECT n.attrID AS attrID, AVG(normValue * o.overallNormValue) AS corr
        FROM Normalized n
        JOIN OverallNorm o ON o.rID = n.rID
        GROUP BY attrID
    )
    SELECT attrID, corr
    FROM Correlation c
    JOIN CourseRatingAttribute cra ON cra.id = c.attrID
    WHERE cra.name != '_Overall';
END;;
DELIMITER ;''', 'compute_suggestions', Obj.function)
]


@sync
async def init_db():
    async with db:
        for sql_query, name, _ in schemas:
            print('Creating "{}"...'.format(name))
            await db.execute(sql_query)


@sync
async def delete_db():
    import warnings
    warnings.filterwarnings("ignore", "Unknown table.*")
    async with db:
        for _, name, obj_type in schemas:
            if obj_type == Obj.table:
                print('Deleting "{}"...'.format(name))
                await db.execute('DROP TABLE IF EXISTS {}'.format(name))
