#!/usr/bin/env python

import sys
import os
import mimetypes
import yaml
from collections import namedtuple
from contextlib import contextmanager

GeventCommand = namedtuple('GeventCommand', 'command contains')

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
    submodules_list = os.listdir(os.path.join(filedir, source_root_parent))
    for d in submodules_list:
        if d == "__init__.py" or d == '.' or d == '..':
            continue
        sys.path.insert(1, os.path.join(filedir, source_root_parent, d))

    sys.path.append(os.path.join(filedir, source_root_parent))


def _set_source_root(source_root):
    filedir = os.path.dirname(__file__)
    sys.path.insert(1, os.path.join(filedir, source_root))


def init_hq_python_path():
    _set_source_root_parent('submodules')
    _set_source_root(os.path.join('corehq', 'ex-submodules'))
    _set_source_root(os.path.join('custom', '_legacy'))


def _should_patch_gevent(args, gevent_commands):
    should_patch = False
    for gevent_command in gevent_commands:
        should_patch = args[1] == gevent_command.command
        if gevent_command.contains:
            should_patch = should_patch and gevent_command.contains in ' '.join(args)
        if should_patch:
            break
    return should_patch


def _should_optimize_ptop(args):
    return (
        'run_ptop' in args and
        '--optimize' in args and
        any(map(lambda arg: arg.startswith('--pillow-name'), args))
    )


def _get_pillow_name(args):
    for arg in args:
        if arg.startswith('--pillow-name'):
            return arg.split('=')[1]


def _get_pillow_dependent_apps(pillow_name):
    with open('./corehq/pillows/pillow_dependencies.yml', 'r+') as f:
        dependencies = yaml.load(f)
        return dependencies[pillow_name]


def set_default_settings_path(argv):
    if len(argv) > 1 and argv[1] == 'test':
        module = 'testsettings'
    else:
        module = 'settings'
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", module)


@contextmanager
def dependent_apps(dependent_apps):
    from django.conf import settings

    _real_installed_apps = settings.INSTALLED_APPS
    print 'overriding settings.INSTALLED_APPS to {}'.format(
        ','.join(dependent_apps)
    )
    settings.INSTALLED_APPS = tuple(dependent_apps)
    try:
        yield
    finally:
        settings.INSTALLED_APPS = _real_installed_apps


if __name__ == "__main__":
    init_hq_python_path()

    # important to apply gevent monkey patches before running any other code
    # applying this later can lead to inconsistencies and threading issues
    # but compressor doesn't like it
    # ('module' object has no attribute 'poll' which has to do with
    # gevent-patching subprocess)
    GEVENT_COMMANDS = (
        GeventCommand('mvp_force_update', None),
        GeventCommand('run_gunicorn', None),
        GeventCommand('preindex_everything', None),
        GeventCommand('prime_views', None),
        GeventCommand('ptop_preindex', None),
        GeventCommand('sync_prepare_couchdb_multi', None),
        GeventCommand('sync_couch_views', None),
        GeventCommand('celery', '-P gevent'),
    )
    if len(sys.argv) > 1 and _should_patch_gevent(sys.argv, GEVENT_COMMANDS):
        from restkit.session import set_session; set_session("gevent")
        from gevent.monkey import patch_all; patch_all(subprocess=True)
        from psycogreen.gevent import patch_psycopg; patch_psycopg()

    # workaround for https://github.com/smore-inc/tinys3/issues/33
    mimetypes.init()

    set_default_settings_path(sys.argv)
    from django.core.management import execute_from_command_line
    if _should_optimize_ptop(sys.argv):
        pillow_name = _get_pillow_name(sys.argv)
        apps = _get_pillow_dependent_apps(pillow_name)
        with dependent_apps(apps):
            execute_from_command_line(sys.argv)
    else:
        execute_from_command_line(sys.argv)
