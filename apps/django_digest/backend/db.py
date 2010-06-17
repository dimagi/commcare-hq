import logging
from datetime import datetime

from django import get_version
from django.conf import settings
from django.contrib.auth.models import User
from django.core import signals
from django.db import backend, connection as global_connection, IntegrityError

from django_digest.models import UserNonce, PartialDigest

_connection = None
_l = logging.getLogger(__name__)

def close_connection(**kwargs):
    if _connection:
        _connection.close()
signals.request_finished.connect(close_connection)
        
def reset_queries(**kwargs):
    if _connection:
        _connection.queries = []
signals.request_started.connect(reset_queries)

def is_test_mode():
    # hack - in tests we want to run within the same transaction
    # as the test case to pick up users created there
    from django.template import Template
    from django.test.utils import instrumented_test_render
    return Template.render.__name__ == 'instrumented_test_render'

def commit():
    if not is_test_mode():
        get_connection().connection.commit()
    
def get_connection():
    global _connection

    if is_test_mode():
        return global_connection

    if not _connection:
        # django1.2 compatibility modification (http://stackoverflow.com/questions/3026647/getting-a-keyerror-in-db-backend-of-django-digest)
        if get_version() < '1.2':
            _connection = backend.DatabaseWrapper({
                    'DATABASE_HOST': settings.DATABASE_HOST,
                    'DATABASE_NAME': settings.DATABASE_NAME,
                    'DATABASE_OPTIONS': settings.DATABASE_OPTIONS,
                    'DATABASE_PASSWORD': settings.DATABASE_PASSWORD,
                    'DATABASE_PORT': settings.DATABASE_PORT,
                    'DATABASE_USER': settings.DATABASE_USER,
                    'TIME_ZONE': settings.TIME_ZONE,
                    })
        else:
            _connection = backend.DatabaseWrapper({
                            'HOST': settings.DATABASE_HOST,
                            'NAME': settings.DATABASE_NAME,
                            'OPTIONS': settings.DATABASE_OPTIONS,
                            'PASSWORD': settings.DATABASE_PASSWORD,
                            'PORT': settings.DATABASE_PORT,
                            'USER': settings.DATABASE_USER,
                            'TIME_ZONE': settings.TIME_ZONE,
                            })

    return _connection

GET_PARTIAL_DIGEST_QUERY = """
SELECT django_digest_partialdigest.login, django_digest_partialdigest.partial_digest
  FROM django_digest_partialdigest
  INNER JOIN auth_user ON auth_user.id = django_digest_partialdigest.user_id
  WHERE django_digest_partialdigest.login = %s
    AND django_digest_partialdigest.confirmed
    AND auth_user.is_active
"""

DELETE_OLDER_THAN_QUERY = """
SELECT django_digest_usernonce.last_used_at FROM django_digest_usernonce
  WHERE django_digest_usernonce.user_id = %s
  ORDER BY django_digest_usernonce.last_used_at DESC LIMIT 1 OFFSET 31
"""

DELETE_EXPIRED_NONCES_QUERY = """
DELETE FROM django_digest_usernonce
  WHERE django_digest_usernonce.last_used_at < %s
"""

UPDATE_EXISTING_NONCE_WITH_COUNT_QUERY = """
UPDATE django_digest_usernonce SET count = %s, last_used_at = %s
  WHERE django_digest_usernonce.nonce = %s
    AND django_digest_usernonce.user_id = %s
    AND django_digest_usernonce.count < %s
"""

UPDATE_EXISTING_NONCE_WITHOUT_COUNT_QUERY = """
UPDATE django_digest_usernonce SET count = NULL, last_used_at = %s
  WHERE django_digest_usernonce.nonce = %s
    AND django_digest_usernonce.user_id = %s
"""

INSERT_NONCE_QUERY = """
INSERT INTO django_digest_usernonce (user_id, nonce, count, last_used_at)
  VALUES (%s, %s, %s, %s)
"""

from django_digest.models import (_after_authenticate as update_partial_digests,
                                  _review_partial_digests as review_partial_digests)

class AccountStorage(object):
    def get_partial_digest(self, username):
        cursor = get_connection().cursor()
        cursor.execute(GET_PARTIAL_DIGEST_QUERY, [username])
        # In MySQL, String comparison is case-insensitive by default.
        # Therefore a second round of filtering is required.
        row = [(row[1]) for row in cursor.fetchall() if row[0] == username]
        commit()
        if not row:
            return None
        return row[0]

    def get_user(self, username):
        # In MySQL, String comparison is case-insensitive by default.
        # Therefore a second round of filtering is required.
        pds = [pd for pd in PartialDigest.objects.filter(
                login=username, user__is_active=True) if pd.login == username]
        if len(pds) == 0:
            return None
        if len(pds) > 1:
            _l.warn("Multiple partial digests found for the login %r" % username)
            return None
        
        return pds[0].user

class NonceStorage(object):
    def _expire_nonces_for_user(self, user):
        cursor = get_connection().cursor()
        cursor.execute(DELETE_OLDER_THAN_QUERY, [user.id])
        row = cursor.fetchone()
        commit()
        if not row:
            return
        delete_older_than = row[0]
        cursor.execute(DELETE_EXPIRED_NONCES_QUERY, [delete_older_than])
        commit()

    def update_existing_nonce(self, user, nonce, nonce_count):
        cursor = get_connection().cursor()

        if nonce_count == None:
            cursor.execute(UPDATE_EXISTING_NONCE_WITHOUT_COUNT_QUERY,
                           [ get_connection().ops.value_to_db_datetime(datetime.now()),
                             nonce, user.id])
        else:
            cursor.execute(UPDATE_EXISTING_NONCE_WITH_COUNT_QUERY,
                           [ nonce_count,
                             get_connection().ops.value_to_db_datetime(datetime.now()),
                             nonce, user.id, nonce_count])
        
        commit()

        # if no rows are updated, either the nonce isn't in the DB, it's for a different
        # user, or the count is bad
        return cursor.rowcount == 1

    def store_nonce(self, user, nonce, nonce_count):
        self._expire_nonces_for_user(user)

        cursor = get_connection().cursor()
        try:
            cursor.execute(INSERT_NONCE_QUERY,
                           [user.id, nonce, nonce_count,
                            get_connection().ops.value_to_db_datetime(datetime.now())])
            return True
        except IntegrityError:
            return False
        finally:
            commit()
