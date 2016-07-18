from django.conf import settings
from sqlalchemy import create_engine
from sqlalchemy.exc import ProgrammingError

from corehq.util.decorators import ContextDecorator


class temporary_database(ContextDecorator):
    """Create a database temporarily and remove it afterwards.
    """
    def __init__(self, database_name):
        self.database_name = database_name
        # use db1 engine to create db2 http://stackoverflow.com/a/8977109/8207
        self.root_engine = create_engine(settings.SQL_REPORTING_DATABASE_URL)

    def __enter__(self):
        conn = self.root_engine.connect()
        conn.execute('commit')
        try:
            conn.execute('CREATE DATABASE {}'.format(self.database_name))
        except ProgrammingError:
            # optimistically assume it failed because was already created.
            pass
        conn.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        conn = self.root_engine.connect()
        conn.execute('rollback')
        try:
            conn.execute('DROP DATABASE {}'.format(self.database_name))
        finally:
            conn.close()
            self.root_engine.dispose()
