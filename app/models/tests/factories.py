import factory

from faker import Faker
from app.models import User as UserDB
from app.services.auth import get_password_hash

from conftest import TestingSessionLocal


faker = Faker()


class UserFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = UserDB
        sqlalchemy_session_factory = TestingSessionLocal
        sqlalchemy_session_persistence = "commit"

    email = faker.email().lower()
    password = get_password_hash("password")
    
