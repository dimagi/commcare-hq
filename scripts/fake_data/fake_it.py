"""
This script generates fake data to use for load testing HQ.
Go through and set the numbers and comment/uncomment as needed.

You can run it by opening a django shell and importing this file

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
from couchforms.signals import successful_form_received
from corehq.apps.users.models import CommCareUser, WebUser, CommCareCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.domain.models import Domain

from .make_users import make_web_user, make_cc_user, make_cc_users
from .submit_forms import make_forms


# Copied from Dan's stuff
def disable_signals():
    print "Disabling signals"
    print len(successful_form_received.receivers)
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
domain_name = 'bigdomain'

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
    user = None
    while not user:
        user = make_cc_user(domain_name)
    make_forms(
        domain_name,
        app_id,
        user,
        cases=random.randint(0, 860),
        avg_updates=3.5
    )


# Make sure you're using the correct db!
pool = Pool(10)
num_users = 500
for i in range(num_users):
    # control verbosity
    # if i%1 == 0:
    print "%d / %d users created (%s%%)" % (
            i, num_users, float(i)/num_users)
    pool.spawn(user_and_forms)


# Estimate 2 hrs to get to 10k users with no cases or forms
# make_cc_users(domain_name, 10000)
