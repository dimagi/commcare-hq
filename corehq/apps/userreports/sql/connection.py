import sqlalchemy
from django.conf import settings


def get_engine():
    return sqlalchemy.create_engine(settings.SQL_REPORTING_DATABASE_URL)





