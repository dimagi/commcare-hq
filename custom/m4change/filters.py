from django.utils.translation import ugettext_noop, ugettext as _

from corehq.apps.reports.filters.base import BaseSingleOptionFilter


class FacilityHmisFilter(BaseSingleOptionFilter):
    slug = "facility_hmis_filter"
    label = ugettext_noop("Facility HMIS Report")
    default_text = None

    @property
    def options(self):
        from custom.m4change.reports import all_hmis_report, anc_hmis_report, immunization_hmis_report, \
            ld_hmis_report

        return [
            ("all", all_hmis_report.AllHmisReport.name),
            ("anc", anc_hmis_report.AncHmisReport.name),
            ("immunization", immunization_hmis_report.ImmunizationHmisReport.name),
            ("ld", ld_hmis_report.LdHmisReport.name),
        ]


class ServiceTypeFilter(BaseSingleOptionFilter):
    slug = "service_type_filter"
    label = ugettext_noop("Service type")
    default_text = None

    @property
    def options(self):
        return [
            ("all", _("All")),
            ("registration", _("registration")),
            ("antenatal", _("antenatal")),
            ("delivery", _("delivery")),
            ("immunization", _("immunization"))
        ]
