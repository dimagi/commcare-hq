#!/usr/bin/env python
import os
import sys

import attr
from gevent import monkey
from psycogreen.gevent import patch_psycopg


def main():
    # important to apply gevent monkey patches before running any other code
    # applying this later can lead to inconsistencies and threading issues
    # but compressor doesn't like it
    # ('module' object has no attribute 'poll' which has to do with
    # gevent-patching subprocess)
    GEVENT_COMMANDS = (
        GeventCommand('run_gunicorn'),
        GeventCommand('run_sql'),
        GeventCommand('run_blob_migration'),
        GeventCommand('check_blob_logs'),
        GeventCommand('preindex_everything'),
        GeventCommand('migrate'),
        GeventCommand('migrate_multi'),
        GeventCommand('prime_views'),
        GeventCommand('ptop_preindex'),
        GeventCommand('sync_prepare_couchdb_multi'),
        GeventCommand('sync_couch_views'),
        GeventCommand('delete_old_couch_views_from_disk'),
        GeventCommand('populate_form_date_modified'),
        GeventCommand('run_aggregation_query'),
        GeventCommand('send_pillow_retry_queue_through_pillows'),
        GeventCommand('run_all_management_command'),
        GeventCommand('copy_events_to_sql', http_adapter_pool_size=32),
        GeventCommand('verify_ssl_connections'),
        GeventCommand('elastic_sync_multiplexed'),
    )
    _patch_gevent_if_required(sys.argv, GEVENT_COMMANDS)

    init_hq_python_path()
    run_patches()

    from corehq.warnings import configure_warnings
    configure_warnings(is_testing(sys.argv))

    set_default_settings_path(sys.argv)
    set_nosetests_verbosity(sys.argv)
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)


@attr.s
class GeventCommand(object):
    command = attr.ib()
    contains = attr.ib(default=None)
    http_adapter_pool_size = attr.ib(default=None)


def _patch_gevent_if_required(args, gevent_commands):
    if len(args) <= 1:
        return
    for gevent_command in gevent_commands:
        should_patch = args[1] == gevent_command.command
        if gevent_command.contains:
            should_patch = should_patch and gevent_command.contains in ' '.join(args)
        if should_patch:
            monkey.patch_all(subprocess=True)
            patch_psycopg()
            if gevent_command.http_adapter_pool_size:
                # requests must be imported after `patch_all()` is called
                import requests
                requests.adapters.DEFAULT_POOLSIZE = gevent_command.http_adapter_pool_size
            break


def init_hq_python_path():
    _set_source_root_parent('submodules')
    _set_source_root_parent('extensions')
    _set_source_root(os.path.join('corehq', 'ex-submodules'))
    _set_source_root(os.path.join('custom', '_legacy'))


def _set_source_root_parent(source_root_parent):
    """
    add everything under `source_root_parent` to the list of source roots
    e.g. if you call this with param 'submodules'
    and you have the file structure

    project/
        submodules/
            foo-src/
                foo/
            bar-src/
                bar/

    (where foo and bar are python modules)
    then foo and bar would become top-level importable

    """
    filedir = os.path.dirname(__file__)
    dir = os.path.join(filedir, source_root_parent)
    if not os.path.exists(dir):
        return

    submodules_list = os.listdir(dir)
    for d in submodules_list:
        if d == "__init__.py" or d == '.' or d == '..':
            continue
        sys.path.insert(1, os.path.join(filedir, source_root_parent, d))

    sys.path.append(os.path.join(filedir, source_root_parent))


def _set_source_root(source_root):
    filedir = os.path.dirname(__file__)
    sys.path.insert(1, os.path.join(filedir, source_root))


def run_patches():
    patch_jsonfield()


def patch_jsonfield():
    """Patch the ``to_python`` method of JSONField
    See https://github.com/bradjasper/django-jsonfield/pull/173 for more details
    """
    import json
    from django.core.exceptions import ValidationError
    from django.utils.translation import gettext_lazy as _
    from jsonfield import JSONField

    def to_python(self, value):
        if isinstance(value, str):
            try:
                return json.loads(value, **self.load_kwargs)
            except ValueError:
                raise ValidationError(_("Enter valid JSON"))
        return value

    JSONField.to_python = to_python


def set_default_settings_path(argv):
    if is_testing(argv):
        os.environ.setdefault('CCHQ_TESTING', '1')
        module = 'testsettings'
    else:
        module = 'settings'
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", module)


def is_testing(argv):
    return len(argv) > 1 and argv[1] == 'test' or os.environ.get('CCHQ_TESTING') == '1'


def set_nosetests_verbosity(argv):
    """Increase nose output verbosity with -v... argument

        -v: print test names
        -vv: do not capture stdout
        -vvv: do not capture logging
        -vvvv: enable nose internal logging
    """
    import logging

    def set_verbosity(arg, i):
        args = []
        verbosity = sum(1 for c in arg if c == "v") + 1
        if len(arg) > verbosity:
            # preserve other single-letter arguments (ex: -xv)
            args.append("".join(c for c in arg if c != "v"))
        if verbosity > 2:
            args.append("--nocapture")
        if verbosity > 3:
            verbosity -= 1
            args.append("--nologcapture")
            logging.basicConfig(level=logging.NOTSET)
            logging.getLogger().info(
                "Adjust logging with testsettings._set_logging_levels")
        args.append("--nose-verbosity=%s" % verbosity)
        argv[i:i + 1] = args

    if len(argv) > 1 and argv[1] == 'test':
        for i, arg in reversed(list(enumerate(argv))):
            if arg[:1] == "-" and arg[1] != "-" and any(c == 'v' for c in arg):
                set_verbosity(arg, i)
                break


if __name__ == "__main__":
    main()
