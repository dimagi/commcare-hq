from __future__ import absolute_import
from __future__ import unicode_literals
import os
import gevent.socket
import redis.connection
from manage import _set_source_root_parent, _set_source_root

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

_set_source_root_parent('submodules')
_set_source_root(os.path.join('corehq', 'ex-submodules'))
_set_source_root(os.path.join('custom', '_legacy'))

redis.connection.socket = gevent.socket
from ws4redis.uwsgi_runserver import uWSGIWebsocketServer
application = uWSGIWebsocketServer()
