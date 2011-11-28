from couchdbkit.ext.django.schema import *
from dimagi.utils.mixins import UnicodeMixIn
from datetime import datetime
from django.shortcuts import render_to_response
from django.template.context import RequestContext

class ReportNotification(Document, UnicodeMixIn):
    domain = StringProperty()
    user_ids = StringListProperty()
    report_slug = StringProperty()
    
    def __unicode__(self):
        return "Notify: %s user(s): %s, report: %s" % \
                (self.doc_type, ",".join(self.user_ids), self.report_slug)
    
class DailyReportNotification(ReportNotification):
    hours = IntegerProperty()
    
    
class WeeklyReportNotification(ReportNotification):
    hours = IntegerProperty()
    day_of_week = IntegerProperty()

import corehq.apps.reports.signals
