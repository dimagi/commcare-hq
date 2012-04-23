from corehq.apps.reports.custom import ReportField

class FacilityNameField(ReportField):
    slug = "facility_name"
    template = "hsph/fields/facility_name.html"

    def update_context(self):
        pass

class NameOfDCOField(ReportField):
    slug = "dco_name"
    template = "hsph/fields/dco_name.html"

    def update_context(self):
        pass

class NameOfDCTLField(ReportField):
    slug = "dctl_name"
    template = "hsph/fields/dctl_name.html"

    def update_context(self):
        pass