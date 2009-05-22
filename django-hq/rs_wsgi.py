import os
import sys

#sys.path.append(os.path.join(os.path.dirname(__file__)))
##sys.path.append(os.path.join(os.path.dirname(__file__),'apps'))
#sys.path.append(os.path.join(os.path.dirname(__file__),'rapidsms'))
#sys.path.append(os.path.join(os.path.dirname(__file__),'rapidsms','apps'))
##sys.path.append(os.path.join(os.path.dirname(__file__),'rapidsms','apps'))

sys.path.append(os.path.join(os.path.dirname(__file__)))
sys.path.append(os.path.join(os.path.dirname(__file__),'apps'))
sys.path.append(os.path.join(os.path.dirname(__file__),'..','rapidsms'))
sys.path.append(os.path.join(os.path.dirname(__file__),'..','rapidsms','apps'))

#rapidsms lib stuff
sys.path.append(os.path.join(os.path.dirname(__file__),'..','rapidsms','lib'))
sys.path.append(os.path.join(os.path.dirname(__file__),'..','rapidsms','lib','rapidsms'))
sys.path.append(os.path.join(os.path.dirname(__file__),'..','rapidsms','lib','rapidsms','webui'))





os.environ['RAPIDSMS_INI'] = os.path.join(os.path.dirname(__file__),'hqsetup.ini')
os.environ['DJANGO_SETTINGS_MODULE'] = 'rapidsms.webui.settings'
from rapidsms.webui import settings

import django.core.handlers.wsgi
application = django.core.handlers.wsgi.WSGIHandler()
