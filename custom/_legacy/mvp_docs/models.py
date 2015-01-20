from casexml.apps.case.models import CommCareCase
from couchforms.models import XFormInstance


class IndicatorXForm(XFormInstance):

    def save(self, **kwargs):
        self.doc_type = 'IndicatorXForm'
        super(IndicatorXForm, self).save(**kwargs)


class IndicatorCase(CommCareCase):

    def save(self, **kwargs):
        self.doc_type = 'IndicatorCase'
        super(IndicatorCase, self).save(**kwargs)
