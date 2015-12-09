import os
from manage import _set_source_root_parent, _set_source_root

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

_set_source_root_parent('submodules')
_set_source_root(os.path.join('corehq', 'ex-submodules'))
_set_source_root(os.path.join('custom', '_legacy'))

# patch gevent
from restkit.session import set_session
from gevent.monkey import patch_all
from psycogreen.gevent import patch_psycopg

set_session("gevent")
patch_all(subprocess=True)
patch_psycopg()

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
