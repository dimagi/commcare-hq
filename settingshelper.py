import os
import tempfile
import uuid


class SharedDriveConfiguration(object):
    def __init__(self, shared_drive_path, restore_dir, transfer_dir, temp_dir):
        self.shared_drive_path = shared_drive_path
        self.restore_dir_name = restore_dir
        self.transfer_dir_name = transfer_dir
        self.temp_dir_name = temp_dir

        self._restore_dir = self._init_dir(restore_dir)
        self.transfer_dir = self._init_dir(transfer_dir)
        self.temp_dir = self._init_dir(temp_dir)
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


def _make_couchdb_tuple(row, couch_database_url):

    if isinstance(row, basestring):
        app_label = row
        return app_label, couch_database_url
    else:
        app_label, postfix = row
        return app_label, '%s__%s' % (couch_database_url, postfix)


def make_couchdb_tuples(config, couch_database_url):
    """
    Helper function to generate couchdb tuples
    for mapping app name to couch database URL.

    """
    return [_make_couchdb_tuple(row, couch_database_url) for row in config]


def get_extra_couchdbs(config, couch_database_url):
    """
    Create a mapping from database prefix to database url

    :param config:              list of database strings or tuples
    :param couch_database_url:  main database url
    """
    extra_dbs = {}
    for row in config:
        if isinstance(row, tuple):
            _, postfix = row
            extra_dbs[postfix] = '%s__%s' % (couch_database_url, postfix)

    return extra_dbs


def celery_failure_handler(task, exc, task_id, args, kwargs, einfo):
    from redis.exceptions import ConnectionError
    from django_redis.exceptions import ConnectionInterrupted
    if isinstance(exc, (ConnectionInterrupted, ConnectionError)):
        task.retry(args=args, kwargs=kwargs, exc=exc, max_retries=3, countdown=60 * 5)
