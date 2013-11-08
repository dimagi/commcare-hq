"""
Fluff calculators that pertain to specific users (workers).
These are used in the Incentive Payment Report
"""
import datetime

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
            if total:
                yield { 
                    'date': form.received_on,
                    'value': total,
                    'group_by': [
                        form.domain,
                        form.metadata.userID,
                    ],
                }


    def get_result(self, key, date_range=None, reduce=True):
        # This block is pretty much a stripped copy-paste from fluff
        # except I needed to make sure the results were unique by case
        assert isinstance(date_range, tuple)
        start, end = date_range
        shared_key = [self.fluff._doc_type] + key + [self.slug, 'total']
        q = self.fluff.view(
            'fluff/generic',
            startkey=shared_key + [json_format_date(start)],
            endkey=shared_key + [json_format_date(end)],
            reduce=False,
        ).all()

        def strip(id_string):
            prefix = '%s-' % self.fluff.__name__
            assert id_string.startswith(prefix)
            return id_string[len(prefix):]

        cases = {}
        for form in q:
            form_id = strip(form['id'])
            case_id = XFormInstance.get(form_id).form['case']['@case_id']
            cases[case_id] = max(cases.get(case_id, 0), form['value'])
        return {'total': sum(cases.values())}

