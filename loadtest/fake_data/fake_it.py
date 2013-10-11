import datetime

from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db

from corehq.apps.users.models import CommCareUser, WebUser, CommCareCase
from corehq.apps.domain.shortcuts import create_domain

from .make_users import make_web_users, make_cc_users
from .cases_and_forms import make_cases, make_forms

db = get_db()

print "Hello!"

# domain1 = create_domain('MySpace')
# make_web_users(domain1.name, 20)
# make_cc_users(domain1.name, 20)
