import datetime

from corehq.apps.users.models import CommCareUser, CommCareCase
import fluff

from .constants import *

# check out form.form['case']['close']

def user_date_group(form, value=1):
    return { 
        'date': form.received_on,
        'value': value,
        'group_by': [
            form.domain,
            form.metadata.userID,
        ],
    }


# group by user!
class WomenRegistered(fluff.Calculator):
    "No. of women registered under BCSP"

    @fluff.date_emitter
    def total(self, form):
        "Open cases at end of month"
        if form.xmlns == DELIVERY_XMLNS:
            children = form.form.get('live_birth_amount')
            if children:
                yield user_date_group(form, children)


class ChildrenRegistered(fluff.Calculator):
    "No. of children registered under BCSP"
    
    @fluff.date_emitter
    def total(self, form):
        "Open cases at end of month"
        if form.xmlns == DELIVERY_XMLNS:
            if form.form.get('mother_preg_outcome') in ['2', '3']:
                yield case_date_group(form)


# class ServiceForms(fluff.Calculator):
#     "Submission of Service Availability form"

# class GrowthMonitoring(fluff.Calculator):
#     "No. of Growth monitoring Sections Filled for eligible children"

