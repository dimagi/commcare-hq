from StringIO import StringIO
from django.test.client import Client
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db

def get_submit_url(domain):
    return "/a/{domain}/receiver/".format(domain=domain)

