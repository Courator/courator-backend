import json
from argparse import ArgumentParser

import requests
import uvicorn

from courator import DEBUG
from .sql_schemas import init_db, delete_db


def main():
    parser = ArgumentParser(description='An app to rate and suggest university courses')
    sp = parser.add_subparsers(dest='action')
    sp.required = True
    sp.add_parser('init')
    sp.add_parser('delete')
    sp.add_parser('run')
    p = sp.add_parser('load')
    p.add_argument('data_json', help='JSON file with list of {"CourseNumber": "CS100", "CourseName": "", "CourseDescription": ""}')
    p.add_argument('auth', help='Authentication in form of username:password')
    p.add_argument('-e', '--existing-only', help="Don't create an account/university if they don't exist")
    p.add_argument('-s', '--server-url', help='URL of server to upload to', default='http://localhost:5000')
    p.add_argument('-u', '--university', help='University code to upload to', default='UIUC')
    args = parser.parse_args()
    if args.action == 'init':
        init_db()
    elif args.action == 'delete':
        delete_db()
    elif args.action == 'load':
        with open(args.data_json) as f:
            courses = json.load(f)
        username, password = args.auth.split(':')
        base = args.server_url.rstrip('/')
        login = lambda: requests.post(base + '/token', data=dict(username=username, password=password, client_id='cli', grant_type='password', scope='account'))
        r = login()
        if not r.ok:
            r2 = None
            if not args.existing_only:
                print('Creating account...')
                r2 = requests.post(base + '/account', json=dict(email=username, password=password))
            if not r2 or not r2.ok:
                print('Failed to authenticate {}: {}'.format(r.status_code, r.content))
                raise SystemExit(1)
            r = login()
            assert r.ok
        token = r.json()['access_token']
        auth_headers = {'Authorization': 'Bearer {}'.format(token)}
        r = requests.get(base + '/university/' + args.university)
        if not r.ok:
            if args.existing_only:
                print('University does not exist')
                raise SystemExit(1)
            print('Creating university...')
            r = requests.post(base + '/university', json=dict(name=args.university, code=args.university), headers=auth_headers)
            assert r.ok

        for course in courses:
            code = course['CourseNumber']
            title = course['CourseName']
            description = course['CourseDescription']
            print('Uploading {}...'.format(code))
            r = requests.post(base + '/university/{}/course'.format(args.university), json=dict(code=code, title=title, description=description), headers=auth_headers)
            if not r.ok:
                print('Failed to upload ({}): {}'.format(r.status_code, r.content))
    elif args.action == 'run':
        log_level = 'info'
        reload = False
        if DEBUG:
            log_level = 'debug'
            reload = True
        uvicorn.run("courator:app", host="0.0.0.0", port=5000, log_level=log_level, reload=reload)


if __name__ == '__main__':
    main()
