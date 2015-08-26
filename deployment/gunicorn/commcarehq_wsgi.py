import os
from manage import _set_source_root_parent, _set_source_root

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

_set_source_root_parent('submodules')
_set_source_root(os.path.join('corehq', 'ex-submodules'))
_set_source_root(os.path.join('custom', '_legacy'))

from restkit.session import set_session; set_session("gevent")
from gevent.monkey import patch_all; patch_all(subprocess=True)
from psycogreen.gevent import patch_psycopg; patch_psycopg()

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
