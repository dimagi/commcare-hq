#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

from django.core.management import execute_manager
import sys, os

filedir = os.path.dirname(__file__)

submodules_list = os.listdir(os.path.join(filedir, 'submodules'))
for d in submodules_list:
    if d == "__init__.py" or d == '.' or d == '..':
        continue
    sys.path.insert(1, os.path.join(filedir, 'submodules', d))

sys.path.append(os.path.join(filedir,'submodules'))

if __name__ == "__main__":
    # proxy for whether we're running gunicorn with -k gevent
    if "gevent" in sys.argv:
        from restkit.session import set_session; set_session("gevent")
        from gevent.monkey import patch_all; patch_all()

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
    from django.core.management import execute_from_command_line
    import couchpulse
    couchpulse.monkey_patch()
    execute_from_command_line(sys.argv)
