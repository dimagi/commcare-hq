from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

import logging
from collections import namedtuple
import os
import sys
import tempfile
import uuid

import re
from django.db.backends.base.creation import TEST_DATABASE_PREFIX
import six
from raven import breadcrumbs
from raven import fetch_git_sha


def is_testing():
    return os.environ.get("CCHQ_TESTING") == "1"


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


def get_couchdb_url(server_root, username, password, dbname, use_https=False):
    if username and password:
        db_params = {
            "username": username,
            "auth_token": password,
            "use_basic_auth": True,
        }
    else:
        # admin party + empty username and auth_token
        db_params = None
    http_method = 'https' if use_https else 'http'
    uri = '{http_method}://{server_root}/{dbname}'.format(**locals())
    return DbUri(uri, db_params)


class DbUri(six.text_type):
    """DB URI string with params attribute

    The `params` attribute is a dict to be passed as keyword arguments
    to `couchdbkit.client.Database` as in `Database(**uri.params)`

    This allows database parameters to be passed with the URL without
    major refactoring to change all the places that reference the URL
    expecting it to be a string. Historically the parameters were
    encoded in the URL.
    """

    __slots__ = ["params"]

    def __new__(cls, uri, db_params):
        obj = super(DbUri, cls).__new__(cls, uri)
        obj.params = {"uri": uri, "db_params": db_params}
        return obj


def get_db_name(dbname, is_test):
    """Get databse name (possibly with test prefix)

    :param is_test: Add test prefix if true.
    """
    if isinstance(dbname, bytes):
        dbname = dbname.decode('utf-8')

    return (TEST_DATABASE_PREFIX + dbname) if is_test else dbname


def assign_test_db_names(dbs):
    """Fix database names for REUSE_DB

    Django automatically uses test database names when testing, but
    only if the test database setup routine is called. This allows us
    to safely skip the test database setup with REUSE_DB.
    """
    for db in dbs.values():
        test_db_name = get_db_name(db['NAME'], True)
        db['NAME'] = db.setdefault('TEST', {}).setdefault('NAME', test_db_name)


class CouchSettingsHelper(namedtuple('CouchSettingsHelper',
                          ['couch_database_configs', 'couchdb_apps', 'extra_db_names', 'unit_testing'])):
    def make_couchdb_tuples(self):
        """
        Helper function to generate couchdb tuples
        for mapping app name to couch database URL.

        """
        return [self._make_couchdb_tuple(row) for row in self.couchdb_apps]

    def _make_couchdb_tuple(self, row):
        if isinstance(row, six.string_types):
            app_label, postfix = row, None
        else:
            app_label, postfix = row
        if postfix:
            return app_label, self._db_url_for_postfix(postfix)
        else:
            return app_label, self.main_db_url

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
            extra_dbs[postfix] = self._db_url_for_postfix(postfix)

        return extra_dbs

    @property
    def main_db_url(self):
        return self.db_urls_by_prefix[None]

    @property
    def db_urls_by_prefix(self):
        if not getattr(self, '_urls_by_prefix', None):
            urls_by_prefix = {}
            for key, config in self.couch_database_configs.items():
                prefix = None if key == 'default' else key
                url = self._get_db_url(config)
                urls_by_prefix[prefix] = url
            self._urls_by_prefix = urls_by_prefix

        return self._urls_by_prefix

    def _db_url_for_postfix(self, postfix):
        if postfix in self.db_urls_by_prefix:
            return self.db_urls_by_prefix[postfix]
        return DbUri(
            '%s__%s' % (self.main_db_url, postfix),
            self.main_db_url.params["db_params"],
        )

    def _get_db_url(self, config):
        return get_couchdb_url(
            config['COUCH_SERVER_ROOT'],
            config['COUCH_USERNAME'],
            config['COUCH_PASSWORD'],
            get_db_name(config['COUCH_DATABASE_NAME'], self.unit_testing),
            use_https=config['COUCH_HTTPS'],
        )


def celery_failure_handler(task, exc, task_id, args, kwargs, einfo):
    from redis.exceptions import ConnectionError
    from django_redis.exceptions import ConnectionInterrupted
    if isinstance(exc, (ConnectionInterrupted, ConnectionError)):
        task.retry(args=args, kwargs=kwargs, exc=exc, max_retries=3, countdown=60 * 5)


def get_allowed_websocket_channels(request, channels):
    from django.core.exceptions import PermissionDenied
    if request.user and request.user.is_authenticated and request.user.is_superuser:
        return channels
    else:
        raise PermissionDenied(
            'Not allowed to subscribe or to publish to websockets without '
            'superuser permissions or domain membership!'
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
                    print("{} logger is being changed to {}".format(
                        handler['class'],
                        'logging.StreamHandler'
                    ), file=sys.stderr)
                handler["class"] = "logging.StreamHandler"


def configure_sentry(base_dir, server_env, pub_key, priv_key, project_id):
    if not (pub_key and priv_key and project_id):
        return

    release = get_release_name(base_dir, server_env)

    breadcrumbs.ignore_logger('quickcache')
    breadcrumbs.ignore_logger('django.template')

    return {
        'dsn': 'https://{pub_key}:{priv_key}@sentry.io/{project_id}'.format(
            pub_key=pub_key,
            priv_key=priv_key,
            project_id=project_id
        ),
        'release': release,
        'environment': server_env,
        'tags': {},
        'include_versions': False,  # performance without this is bad
        'processors': (
            'raven.processors.RemovePostDataProcessor',
            'corehq.util.sentry.HQSanitzeSystemPasswordsProcessor',
        ),
        'ignore_exceptions': [
            'KeyboardInterrupt'
        ],
        'CELERY_LOGLEVEL': logging.FATAL
    }


def get_release_name(base_dir, server_env):
    release_dir = base_dir.split('/')[-1]
    if re.match('\d{4}-\d{2}-\d{2}_\d{2}.\d{2}', release_dir):
        release = "{}-{}-deploy".format(release_dir, server_env)
    else:
        release = fetch_git_sha(base_dir)
    return release
