import json
from argparse import ArgumentParser

import httpx
import uvicorn

from courator import DEBUG
from .sql_schemas import init_db, delete_db


def get_token(auth, server_url, existing_only=False):
    username, password = auth.split(':')
    base = server_url.rstrip('/')
    login = lambda: httpx.post(base + '/token',
                               data=dict(username=username, password=password, client_id='cli', grant_type='password',
                                         scope='account'))
    r = login()
    if r.is_error:
        r2 = None
        if not existing_only:
            print('Creating account...')
            r2 = httpx.post(base + '/account', json=dict(email=username, password=password))
        if not r2 or r2.is_error:
            print('Failed to authenticate {}: {}'.format(r.status_code, r.content))
            raise SystemExit(1)
        r = login()
        assert not r2.is_error
    return r.json()['access_token']


def main():
    parser = ArgumentParser(description='An app to rate and suggest university courses')
    sp = parser.add_subparsers(dest='action')
    sp.required = True
    sp.add_parser('init')
    sp.add_parser('delete')
    p = sp.add_parser('run')
    p.add_argument('-p', '--port', help='Port to run on. Default: 8001', type=int, default=8001)
    p = sp.add_parser('load')
    p.add_argument('data_json',
                   help='JSON file with list of {"CourseNumber": "CS100", "CourseName": "", "CourseDescription": ""}')
    p.add_argument('university', help='University code to upload to')
    p.add_argument('auth', help='Authentication in form of username:password')
    p.add_argument('-e', '--existing-only', help="Don't create an account/university if they don't exist")
    p.add_argument('-s', '--server-url', help='URL of server to upload to', default='http://localhost:8001')
    p = sp.add_parser('add-default', help='Add default attributes')
    p.add_argument('-s', '--server-url', help='URL of server to upload to', default='http://localhost:8001')
    p.add_argument('auth', help='Authentication in form of username:password')
    args = parser.parse_args()
    if args.action == 'init':
        init_db()
    elif args.action == 'delete':
        delete_db()
    elif args.action == 'load':
        with open(args.data_json) as f:
            courses = json.load(f)
        base = args.server_url.rstrip('/')
        token = get_token(args.auth, args.server_url, args.existing_only)
        auth_headers = {'Authorization': 'Bearer {}'.format(token)}
        r = httpx.get(base + '/university/' + args.university)
        if r.is_error:
            if args.existing_only:
                print('University does not exist')
                raise SystemExit(1)
            print('Creating university...')
            r = httpx.post(base + '/university', json=dict(name=args.university, code=args.university),
                           headers=auth_headers)
            assert not r.is_error

        for course in courses:
            code = course['CourseNumber']
            title = course['CourseName']
            description = course['CourseDescription']
            print('Uploading {}...'.format(code))
            r = httpx.post(base + '/university/{}/course'.format(args.university),
                           json=dict(code=code, title=title, description=description), headers=auth_headers)
            if r.is_error:
                print('Failed to upload ({}): {}'.format(r.status_code, r.content))
    elif args.action == 'add-default':
        base = args.server_url.rstrip('/')
        token = get_token(args.auth, args.server_url)
        auth_headers = {'Authorization': 'Bearer {}'.format(token)}
        defaults_attributes = [
            {'name': 'Difficulty', 'description': 'How hard you found the course'},
            {'name': 'Curriculum', 'description': 'How well the course was layed out'},
            {'name': 'Usefulness', 'description': 'How applicable the course is to the real world'},
            {'name': '_Overall', 'description': 'Overall course rating'}
        ]
        for attr in defaults_attributes:
            print('Uploading attribute "{}"...'.format(attr['name']))
            r = httpx.post(base + '/ratingAttribute', json=attr, headers=auth_headers)
            if r.is_error:
                print('Failed to upload attribute {} ({}): {}'.format(attr, r.status_code, r.content))
    elif args.action == 'run':
        log_level = 'info'
        reload = False
        if DEBUG:
            log_level = 'debug'
            reload = True
        uvicorn.run("courator:app", host="0.0.0.0", port=args.port, log_level=log_level, reload=reload)


if __name__ == '__main__':
    main()
