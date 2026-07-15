#!/bin/bash
set -e  # Exit if any command fails

source venv/bin/activate

git pull

pip install -r requirements.txt

# apply migration
alembic upgrade head
echo "✅ 1/3 Successfully Applied Database Migration"

lsof -ti :9090 | xargs --no-run-if-empty kill -9
echo "✅ 2/3 Kill the Former Process on the Same Port"

# start the Web App again
nohup uvicorn app.main:app --host 0.0.0.0 --port 9090 --forwarded-allow-ips="127.0.0.1" > uvicorn.log 2>&1 &
echo "✅ 3/3 Deployment successful!"
