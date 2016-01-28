from collections import namedtuple
import os
import sys
import tempfile
import uuid

from django.db.backends.creation import TEST_DATABASE_PREFIX


def is_testing():
    return len(sys.argv) > 1 and sys.argv[1] == "test"


class SharedDriveConfiguration(object):
    def __init__(self, shared_drive_path, restore_dir, transfer_dir, temp_dir, blob_dir):
        self.shared_drive_path = shared_drive_path
        self.restore_dir_name = restore_dir
        self.transfer_dir_name = transfer_dir
        self.temp_dir_name = temp_dir
        self.blob_dir_name = blob_dir

        self._restore_dir = self._init_dir(restore_dir)
        self.transfer_dir = self._init_dir(transfer_dir)
        self.temp_dir = self._init_dir(temp_dir)
        self.blob_dir = self._init_dir(blob_dir)
        self.tzmigration_planning_dir = self._init_dir('tzmigration-planning')

    def _init_dir(self, name):
        if not self.shared_drive_path or not os.path.isdir(self.shared_drive_path) or not name:
            return None

        path = os.path.join(self.shared_drive_path, name)
        if not os.path.exists(path):
            os.mkdir(path)
        elif not os.path.isdir(path):
            raise Exception('Shared folder is not a directory: {}'.format(name))

        return path

    def get_unset_reason(self, name):
        if not self.shared_drive_path:
            return "invalid shared drive path: %r" % (self.shared_drive_path,)
        if not os.path.isdir(self.shared_drive_path):
            return "shared drive path is not a directory: %r" % (self.shared_drive_path,)
        directory = getattr(self, name + "_name")
        if not directory:
            return name + " is empty or not configured in settings"
        return None

    @property
    def restore_dir(self):
        return self._restore_dir or tempfile.gettempdir()

    @property
    def transfer_enabled(self):
        from django_transfer import is_enabled
        return is_enabled() and self.transfer_dir

    def get_temp_file(self, suffix="", prefix="tmp"):
        name = '{}{}{}'.format(prefix, uuid.uuid4().hex, suffix)
        return os.path.join(self.temp_dir, name)


def get_server_url(http_method, server_root, username, password):
    if username and password:
        return '%(http_method)s://%(user)s:%(pass)s@%(server)s' % {
            'http_method': http_method,
            'user': username,
            'pass': password,
            'server': server_root,
        }
    else:
        return '%(http_method)s://%(server)s' % {
            'http_method': http_method,
            'server': server_root,
        }


def get_dynamic_db_settings(server_root, username, password, dbname,
                            use_https=False):
    """
    Get dynamic database settings.
    Other apps can use this if they want to change settings

    """

    http_method = 'https' if use_https else 'http'
    server_url = get_server_url(http_method, server_root, username, password)
    database = '%(server)s/%(database)s' % {
        'server': server_url,
        'database': dbname,
    }
    return {
        'COUCH_SERVER':  server_url,
        'COUCH_DATABASE': database,
    }


def get_db_name(dbname, is_test):
    """Get databse name (possibly with test prefix)

    :param is_test: Add test prefix if true.
    """
    return (TEST_DATABASE_PREFIX + dbname) if is_test else dbname


class CouchSettingsHelper(namedtuple('CouchSettingsHelper',
                          ['couch_database_url', 'couchdb_apps', 'extra_db_names'])):
    def make_couchdb_tuples(self):
        """
        Helper function to generate couchdb tuples
        for mapping app name to couch database URL.

        """
        return [self._make_couchdb_tuple(row) for row in self.couchdb_apps]

    def _format_db_uri(self, db_uri):
        return db_uri

    def _make_couchdb_tuple(self, row):
        if isinstance(row, basestring):
            app_label, postfix = row, None
        else:
            app_label, postfix = row
        if postfix:
            return app_label, self._format_db_uri('%s__%s' % (self.couch_database_url, postfix))
        else:
            return app_label, self._format_db_uri(self.couch_database_url)

    def get_extra_couchdbs(self):
        """
        Create a mapping from database prefix to database url

        """
        extra_dbs = {}
        postfixes = []
        for row in self.couchdb_apps:
            if isinstance(row, tuple):
                _, postfix = row
                if postfix:
                    postfixes.append(postfix)

        postfixes.extend(self.extra_db_names)
        for postfix in postfixes:
            extra_dbs[postfix] = self._format_db_uri('%s__%s' % (self.couch_database_url, postfix))

        return extra_dbs


def celery_failure_handler(task, exc, task_id, args, kwargs, einfo):
    from redis.exceptions import ConnectionError
    from django_redis.exceptions import ConnectionInterrupted
    if isinstance(exc, (ConnectionInterrupted, ConnectionError)):
        task.retry(args=args, kwargs=kwargs, exc=exc, max_retries=3, countdown=60 * 5)


def get_allowed_websocket_channels(request, channels):
    from django.core.exceptions import PermissionDenied
    if request.user and request.user.is_authenticated() and request.user.is_superuser:
        return channels
    else:
        raise PermissionDenied(
            'Not allowed to subscribe or to publish to websockets without superuser permissions!'
        )


def fix_logger_obfuscation(fix_logger_obfuscation_, logging_config):
    if fix_logger_obfuscation_:
        # this is here because the logging config cannot import
        # corehq.util.log.HqAdminEmailHandler, for example, if there
        # is a syntax error in any module imported by corehq/__init__.py
        # Setting FIX_LOGGER_ERROR_OBFUSCATION = True in
        # localsettings.py will reveal the real error.
        # Note that changing this means you will not be able to use/test anything
        # related to email logging.
        for handler in logging_config["handlers"].values():
            if handler["class"].startswith("corehq."):
                if fix_logger_obfuscation_ != 'quiet':
                    print "{} logger is being changed to {}".format(
                        handler['class'],
                        'logging.StreamHandler'
                    )
                handler["class"] = "logging.StreamHandler"
