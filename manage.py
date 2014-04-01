#!/usr/bin/env python

import sys
import os


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


if __name__ == "__main__":

    _set_source_root_parent('submodules')
    _set_source_root(os.path.join('corehq', 'ex-submodules'))
    _set_source_root(os.path.join('custom', '_legacy'))

    # proxy for whether we're running gunicorn with -k gevent
    if "gevent" in sys.argv:
        from restkit.session import set_session; set_session("gevent")
        from gevent.monkey import patch_all; patch_all()

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
