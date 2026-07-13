# Type the Following Commands as Short Cuts to the Longer Commands

run-local:
	fastapi dev app/main.py

# Production: --proxy-headers makes rate limiting and logging see the real
# client IP behind a load balancer. Restrict --forwarded-allow-ips to your
# proxy's address(es) instead of "*" in a real deployment.
run-prod:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="*"

test-local:
	pytest -s --cov

apply-migration:
	alembic upgrade head

coverage-report:
	coverage report

coverage-html:
	coverage report && coverage html
