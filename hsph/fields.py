from corehq.apps.reports.custom import ReportField
from corehq.apps.reports.fields import SelectCHWField
from dimagi.utils.couch.database import get_db

class FacilityNameField(ReportField):
    slug = "facility"
    template = "hsph/fields/facility_name.html"

    def update_context(self):
        facilities = self.getFacilties()
        self.context['facilities'] = facilities
        self.context['selected_facility'] = self.request.GET.get(self.slug, '')
        self.context['slug'] = self.slug

    @classmethod
    def getFacilties(cls):
        try:
            data = get_db().view('hsph/dco_facilities',
                reduce=True,
                group=True
            ).all()
            return [item.get('key','')[0] for item in data]
        except KeyError:
            return []

class NameOfDCOField(SelectCHWField):
    slug = "dco_name"
    template = "reports/fields/select_chw.html"

    def update_context(self):
        super(NameOfDCOField, self).update_context()
        self.context['field_name'] = "Name of DCO"
        self.context['default_option'] = "All DCOs"


class NameOfDCTLField(ReportField):
    slug = "dctl_name"
    template = "hsph/fields/dctl_name.html"

    def update_context(self):
        pass