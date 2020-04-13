from argparse import ArgumentParser

from courator.schema import delete_db

from .schema import init_db


def main():
    parser = ArgumentParser(description='An app to rate and suggest university courses')
    sp = parser.add_subparsers(dest='action')
    sp.required = True
    sp.add_parser('init')
    sp.add_parser('delete')
    sp.add_parser('run-dev')
    args = parser.parse_args()
    if args.action == 'init':
        init_db()
    elif args.action == 'delete':
        delete_db()
    elif args.action == 'run-dev':
        from courator import app
        app.run(debug=True)


if __name__ == '__main__':
    main()
