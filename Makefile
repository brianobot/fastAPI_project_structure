# Type the Following Commands as Short Cuts to the Longer Commands

run-local:
	fastapi dev app/main.py

# Production: --proxy-headers makes rate limiting and logging see the real
# client IP. --forwarded-allow-ips must list ONLY your proxy's address(es) -
# never "*", which lets any client spoof X-Forwarded-For and bypass rate
# limiting. Default below trusts a co-located (loopback) proxy; change it to
# your proxy's real IP/CIDR.
run-prod:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="127.0.0.1"

test-local:
	pytest -s --cov

apply-migration:
	alembic upgrade head

coverage-report:
	coverage report

coverage-html:
	coverage report && coverage html
