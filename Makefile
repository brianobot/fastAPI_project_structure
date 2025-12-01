# Type the Following Commands as Short Cuts to the Longer Commands

run-local:
	fastapi dev app/main.py

test-local:
	pytest -s --cov

apply-migration:
	alembic upgrade head
	
coverage-report:
	coverage report

coverage-html:
	coverage report && coverage html