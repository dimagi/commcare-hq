"""
This script generates fake data to use for load testing HQ.
Go through and set the numbers and comment/uncomment as needed.

You can run it either by opening a django shell and importing this file,
or using the perf_script.py file

First:
Configure db settings to use "performance test" db
Turn off debug mode
"""

from gevent import monkey
monkey.patch_all()

import datetime, random

from gevent.pool import Pool

from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db
from receiver.signals import successful_form_received
from corehq.apps.users.models import CommCareUser, WebUser, CommCareCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.domain.models import Domain

from .make_users import make_web_user, make_cc_user
from .submit_forms import make_forms

db = get_db()

# Copied from Dan's stuff
def disable_signals():
    print "Disabling signals"
    print len(successful_form_received.receivers)
    from casexml.apps.phone.signals import send_default_response
    successful_form_received.disconnect(send_default_response)
    from corehq.apps.app_manager.signals import get_custom_response_message
    successful_form_received.disconnect(get_custom_response_message)
    from corehq.apps.receiverwrapper.signals import create_case_repeat_records,\
        create_short_form_repeat_records, create_form_repeat_records
    from casexml.apps.case.signals import case_post_save
    successful_form_received.disconnect(create_form_repeat_records)
    successful_form_received.disconnect(create_short_form_repeat_records)
    case_post_save.disconnect(create_case_repeat_records)
    print "successful_form_received signals truncated: %d" % len(successful_form_received.receivers)

disable_signals()

########################
# Domain and App setup #
########################

# domain = create_domain(domain_name)
domain_name = 'esoergel'

# I copied this app over from HQ
# https://www.commcarehq.org/a/amelia/apps/view/dec1dc1a2c1e16f41b42aca3f60d1334/?lang=en
# the forms are based on that app.
app_id = 'eb70e5a3780f7fc40792ac951f8afd51'

##################
# Make Web Users #
##################

# for i in range(1000):
    # make_web_user(domain_name, number=i)


########################
# Make Users and Forms #
########################

def user_and_forms():
    user = make_cc_user(domain_name)

    make_forms(
        domain_name,
        app_id,
        user,
        cases=random.randint(0,200),
        avg_updates=2
    )
    # print "created user %s" % user.username



pool = Pool(10)

# Make sure you're using the correct db!
num_users = 10000
for i in range(num_users):
    # control verbosity
    if i%100 == 0:
        print "%d / %d users created (%s%%)" % (
                i, num_users, float(i)/num_users)
    pool.spawn(user_and_forms)
