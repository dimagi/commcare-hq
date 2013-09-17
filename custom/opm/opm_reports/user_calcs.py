"""
Fluff calculators that pertain to specific users (workers).
These are used in the Incentive Payment Report
"""
import datetime

from corehq.apps.users.models import CommCareUser, CommCareCase
import fluff

from .constants import *


def user_date_group(form, value=1):
    return { 
        'date': form.received_on,
        'value': value,
        'group_by': [
            form.domain,
            form.metadata.userID,
        ],
    }


class WomenRegistered(fluff.Calculator):
    """
    "No. of women registered under BCSP"

    Value represents the number of children delivered by that case
    """

    @fluff.null_emitter
    def total(self, case):
        if case.type == "Pregnancy":
            total = 0
            for form in case.get_forms():
                if form.xmlns == DELIVERY_XMLNS:
                    children = form.form.get('live_birth_amount')
                    if children:
                        total += int(children)
            yield { 
                'date': None,
                'value': total,
                'group_by': [
                    case.domain,
                    case.user_id,
                ],
            }


class ServiceForms(fluff.Calculator):
    """
    "Submission of Service Availability form"

    Number of Service Availability Forms Filled Out in Time Period
    """

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns == VHND_XMLNS:
            yield user_date_group(form) 


class GrowthMonitoring(fluff.Calculator):
    """
    "No. of Growth monitoring Sections Filled for eligible children"

    Sum of form property (in child followup form) where child1_child_growthmon,
    child2_child_growthmon, and child3_child_growthmon = '1' in the time period.
    Within a form, if multiple = '1', give xtimes the amount. "Union" this so
    that if ever '1' within the time period, that this triggers payment
    """

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns == CHILD_FOLLOWUP_XMLNS:
            # child<n>_child_growthmon == 1 if weight was monitored this month
            total = 0
            for child_num in list('123'):
                child = form.form.get('child_%s' % child_num)
                if child:
                    try:
                        total += int(child.get('child%s_child_growthmon' % child_num))
                    except:
                        pass
            yield user_date_group(form, total)
