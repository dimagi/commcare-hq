# flake8: noqa: E402
import os
from manage import init_hq_python_path, run_patches

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

init_hq_python_path()
# patch gevent
from gevent.monkey import patch_all
from psycogreen.gevent import patch_psycopg

patch_all(subprocess=True)
patch_psycopg()

run_patches()

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
