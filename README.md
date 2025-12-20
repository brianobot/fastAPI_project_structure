# FastAPI Project Structure Template

This repository provides a clean and scalable template for building FastAPI applications. It is designed to help you start new projects quickly with best practices in mind.

## Features
- Organized project structure
- Environment configuration
- Dependency management
- Initial User Model and User Authentication Endpoints with Unit Tests
- Unit Test Configuration with Pytest (With Async Support)
- Alembic Data Migration Configuration


## Getting Started
In order to get started with the FastAPI Project, follow the following steps
- [ ] Create an .env file from the .env.example file and provide values for missing environment variables
      - 1. Update the DATABASE_URL to point at an accessible DATABASE server
      - 2. Update the MAIL_CONFIG section to include mail server credentials
- [ ] Install ```make``` if you do not already have it and run the command ```make run-local``` to start you local server
- [ ] Apply Initial Database Migration for Ensure Database Connection string is valid
      ```bash
      alembic upgrade head
      ```
- [ ] Ensure the Setup Is Complete and Sucessful by Running the following command
      ```bash
      make test-local
      ```
      If all the tests pass successfully you're good to start working on your project.

- [ ] Start Local Server with the following command
      ```bash
      make run-local
      ```


## Project Structure

```
fastapi-project-structure/
.
├── Makefile
├── app
│   ├── __init__.py
│   ├── api_router.py
│   ├── database.py
│   ├── dependencies.py
│   ├── logger.py
│   ├── main.py
│   ├── middlewares.py
│   ├── models
│   │   ├── __init__.py
│   │   └── auth.py
│   ├── routers
│   │   ├── __init__.py
│   │   └── auth.py
│   ├── schemas
│   │   ├── __init__.py
│   │   └── auth.py
│   ├── services
│   │   ├── __init__.py
│   │   └── auth.py
│   └── settings.py
├── logs
└── requirements.txt
```

## How to Download Complete Project Structure from Github

1. **Clone the repository:**
    ```bash
    git clone https://github.com/brianobot/fastAPI_project_structure.git
    cd fastAPI_project_structure
    ```
  
2. **Create & Activate Virtual Environment to Manage Project Dependency In Isolation**
    ```bash
    python3 -m venv venv && source venv/bin/activate #for unix computers 
    ```

3. **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4. **Run the application:**
    ```bash
    make run-local # or uvicorn app.main:app --reload
    ```

5. **Access the API docs:**
    - Open [http://localhost:8000/docs](http://localhost:8000/docs) in your browser.


## Testing
Run initial tests using pytest:
```bash
make test-local # or pytest
```

or 

Run Specific tests 
```bash
pytest -s app/routers/tests/test_auth.py
```

## Environment Variables

Copy `.env.example` to `.env` and update the values as needed.


## Contributing

Contributions are welcome! Please open issues or submit pull requests.
