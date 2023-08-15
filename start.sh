#!/usr/bin/env bash

cd /code/data/xyz
exec python -m http.server 8000 &
cd /code
exec python3 server.py