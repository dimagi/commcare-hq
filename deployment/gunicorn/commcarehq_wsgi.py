# flake8: noqa: E402
import os
from manage import _set_source_root_parent, _set_source_root, run_patches

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

_set_source_root_parent('submodules')
_set_source_root(os.path.join('corehq', 'ex-submodules'))
_set_source_root(os.path.join('custom', '_legacy'))

# patch gevent
from gevent.monkey import patch_all
from psycogreen.gevent import patch_psycopg

patch_all(subprocess=True)
patch_psycopg()

run_patches()

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
