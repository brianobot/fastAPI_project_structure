# FastAPI Project Structure Template

This repository provides a clean and scalable template for building FastAPI applications. It is designed to help you start new projects quickly with best practices in mind.

## Features

- Organized project structure
- Environment configuration
- Dependency management
- Initial User Model and User Authentication Endpoints with Unit Tests
- Unit Test Configuration with Pytest (With Async Support)
- Alembic Data Migration Configuration


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

## Getting Started

1. **Clone the repository:**
    ```bash
    git clone https://github.com/brianobot/fastAPI_project_structure.git
    cd fastAPI_project_structure
    ```

2. **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3. **Run the application:**
    ```bash
    make run-local # or uvicorn app.main:app --reload
    ```

4. **Access the API docs:**
    - Open [http://localhost:8000/docs](http://localhost:8000/docs) in your browser.

## Testing

Run tests using pytest:
```bash
pytest
```

## Environment Variables

Copy `.env.example` to `.env` and update the values as needed.


## Contributing

Contributions are welcome! Please open issues or submit pull requests.
