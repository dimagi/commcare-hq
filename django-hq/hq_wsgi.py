import os
import sys


filedir = os.path.dirname(__file__)
sys.path.append('..')

sys.path.append(os.path.join(filedir))
sys.path.append(os.path.join(filedir,'apps'))
sys.path.append(os.path.join(filedir,'..','rapidsms'))
sys.path.append(os.path.join(filedir,'..','rapidsms','apps'))

#rapidsms lib stuff
sys.path.append(os.path.join(filedir,'..','rapidsms','lib'))
sys.path.append(os.path.join(filedir,'..','rapidsms','lib','rapidsms'))
sys.path.append(os.path.join(filedir,'..','rapidsms','lib','rapidsms','webui'))


os.environ['RAPIDSMS_INI'] = os.path.join(os.path.dirname(__file__),'local.ini')
os.environ['DJANGO_SETTINGS_MODULE'] = 'rapidsms.webui.settings'
os.environ["RAPIDSMS_HOME"] = os.path.abspath(os.path.dirname(__file__))
#os.environ["RAPIDSMS_HOME"] = os.path.join(os.path.abspath(os.path.dirname(__file__)),'..','rapidsms','lib')

from rapidsms.webui import settings

import django.core.handlers.wsgi
application = django.core.handlers.wsgi.WSGIHandler()
