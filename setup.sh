#!/usr/bin/env bash

#############################################
set -e; cd "$(dirname "$0")" # Script Start #
#############################################


[[ -f .venv/bin/python ]] || python3 -m venv --without-pip .venv/
[[ -f .venv/bin/pip ]] || curl https://bootstrap.pypa.io/get-pip.py | .venv/bin/python

.venv/bin/pip install -e .
.venv/bin/pip install gunicorn 'werkzeug==0.16.0'  # Temporary problem with latest wekzeug

