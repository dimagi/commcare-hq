import os
import gevent.socket
import redis.connection
from manage import init_hq_python_path, run_patches

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

init_hq_python_path()
run_patches()

redis.connection.socket = gevent.socket
from ws4redis.uwsgi_runserver import uWSGIWebsocketServer
application = uWSGIWebsocketServer()
