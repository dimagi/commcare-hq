"""
Fluff calculators that pertain to specific users (workers).
These are used in the Incentive Payment Report
"""
import fluff
from couchforms.models import XFormInstance
from corehq.apps.users.models import CommCareUser, CommCareCase
from dimagi.utils.parsing import json_format_date

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

    Value represents the number of women delivered by that case
    """
    @fluff.date_emitter
    def total(self, case):
        if case.type == "Pregnancy":
            yield case.opened_on

class ChildrenRegistered(fluff.Calculator):
    """
    "No. of children registered under BCSP"

    Value represents the number of children delivered by that case
    """

    @fluff.date_emitter
    def total(self, case):
        if case.type == "Pregnancy":
            total = 0
            for form in case.get_forms():
                if form.xmlns == DELIVERY_XMLNS:
                    children = form.form.get('live_birth_amount')
                    if children:
                        total += int(children)
            yield { 'date': case.opened_on, 'value': total }


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
    Number of Growth Monitoring Calculator forms submitted
    """

    @fluff.date_emitter
    def total(self, form):
        if form.xmlns == GROWTH_MONITORING_XMLNS:

            yield {
                'date': form.received_on,
                'group_by': [
                    form.domain,
                    form.metadata.userID,
                ],
            }
