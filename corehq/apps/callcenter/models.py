import datetime
import fluff
from casexml.apps.case.models import CommCareCase

A_DAY = datetime.timedelta(days=1)


class CallCenterCaseCalc(fluff.Calculator):
    def filter(self, item):
        return item.actions and item.actions[0].user_id is not None

    @fluff.date_emitter
    def total(self, case):
        seenUsers = []
        for action in reversed(case.actions):
            user = action.user_id

            if user and user not in seenUsers:
                seenUsers.append(user)
                yield dict(date=action.date, group_by=[case.domain, case.type, user])


class CallCenterFluff(fluff.IndicatorDocument):
    document_class = CommCareCase

    domains = ()
    group_by = ()

    case_modifications = CallCenterCaseCalc(A_DAY)

    class Meta:
        app_label = 'callcenter'


CallCenterFluffPillow = CallCenterFluff.pillow()

from .signals import *
