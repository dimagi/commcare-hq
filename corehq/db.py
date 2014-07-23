from django.conf import settings
from sqlalchemy.engine import create_engine
from sqlalchemy.orm.scoping import scoped_session
from sqlalchemy.orm.session import sessionmaker
from django.core import signals

_engine = create_engine(settings.SQL_REPORTING_DATABASE_URL)
_session_factory = sessionmaker(bind=_engine)

Session = scoped_session(_session_factory)


# Register an event that closes the database connection
# when a Django request is finished.
# This will rollback any open transactions.
def _close_connection(**kwargs):
    Session.remove()

signals.request_finished.connect(_close_connection)