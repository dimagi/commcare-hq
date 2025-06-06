import logging
import os
import re
import subprocess
import sys
import tempfile
import uuid
from collections import namedtuple

from django.db.backends.base.creation import TEST_DATABASE_PREFIX


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
        'COUCH_SERVER': server_url,
        'COUCH_DATABASE': database,
    }


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
        if isinstance(row, tuple):
            app_label, postfix = row
        else:
            app_label, postfix = row, None
        if postfix:
            if postfix in self.db_urls_by_prefix:
                url = self.db_urls_by_prefix[postfix]
            else:
                url = '%s__%s' % (self.main_db_url, postfix)
            return app_label, url
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
            if postfix in self.db_urls_by_prefix:
                url = self.db_urls_by_prefix[postfix]
            else:
                url = '%s__%s' % (self.main_db_url, postfix)
            extra_dbs[postfix] = url

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

    def _get_db_url(self, config):
        return get_dynamic_db_settings(
            config['COUCH_SERVER_ROOT'],
            config['COUCH_USERNAME'],
            config['COUCH_PASSWORD'],
            get_db_name(config['COUCH_DATABASE_NAME'], self.unit_testing),
            use_https=config['COUCH_HTTPS'],
        )["COUCH_DATABASE"]


def celery_failure_handler(task, exc, task_id, args, kwargs, einfo):
    from django_redis.exceptions import ConnectionInterrupted
    from redis.exceptions import ConnectionError
    if isinstance(exc, (ConnectionInterrupted, ConnectionError)):
        task.retry(args=args, kwargs=kwargs, exc=exc, max_retries=3, countdown=60 * 5)


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


def configure_sentry(server_env, dsn, release):
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import ignore_logger
    from sentry_sdk.integrations.redis import RedisIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    def _before_send(event, hint):
        # can't import this during load since settings is not fully configured yet
        from corehq.util.sentry import before_sentry_send
        return before_sentry_send(event, hint)

    ignore_logger('quickcache')
    ignore_logger('django.template')
    ignore_logger('pillowtop')
    ignore_logger('restore')
    ignore_logger('kafka.conn')

    sentry_sdk.init(
        dsn,
        release=release,
        environment=server_env,
        max_request_body_size='never',
        before_send=_before_send,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            SqlalchemyIntegration(),
            RedisIntegration()
        ]
    )


def get_release_name(base_dir, server_env):
    """Return the release name. This should match the name of the release
    created by commcare-cloud
    """
    release_dir = base_dir.split('/')[-1]
    if re.match(r'\d{4}-\d{2}-\d{2}_\d{2}.\d{2}', release_dir):
        return "{}-{}".format(release_dir, server_env)
    else:
        return get_git_commit(base_dir) or 'unknown'


def get_git_commit(base_dir):
    try:
        out = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=base_dir)
        return out.strip().decode('ascii')
    except (OSError, subprocess.CalledProcessError):
        pass


def update_redis_location_for_tests(settings_caches):
    if not is_testing():
        raise Exception("Attempt to update Redis settings outside of tests")

    for name, config in settings_caches.items():
        if not config.get("BACKEND", "").startswith("django_redis"):
            continue

        test_location = config.get("TEST_LOCATION")
        if test_location:
            config["LOCATION"] = test_location
        else:
            logging.warning(
                "Unable to set Redis DB in '%(name)s' cache for tests. Using '%(location)s'.\n"
                "\tTo configure a separate Redis DB for tests add a 'TEST_LOCATION' to the"
                " '%(name)s' cache configuration.", {"name": name, "location": config["LOCATION"]}
            )
