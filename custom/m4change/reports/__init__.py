from django.utils.translation import ugettext as _
from corehq.apps.locations.models import Location


def validate_report_parameters(parameters, config):
    for parameter in parameters:
        if not parameter in config:
            raise KeyError(_("Parameter '%s' is missing" % parameter))


def _is_location_CCT(location):
    return location.metadata.get("CCT", "").lower() == "true"


# A workaround to the problem occurring if a user selects 'All' in the first location filter dropdown
def get_location_hierarchy_by_id(location_id, domain, CCT_only=False):
    if location_id is None or len(location_id) == 0:
        return [location.get_id for location in Location.by_domain(domain) if not CCT_only or _is_location_CCT(location)]
    else:
        user_location = Location.get(location_id)
        locations = [location.get_id for location in user_location.descendants if not CCT_only or _is_location_CCT(location)]
        if not CCT_only or _is_location_CCT(user_location):
            locations.insert(0, user_location.get_id)
        return locations

from custom.m4change.reports import anc_hmis_report, ld_hmis_report, immunization_hmis_report, all_hmis_report,\
    project_indicators_report, mcct_monthly_aggregate_report, aggregate_facility_web_hmis_report, mcct_project_review

CUSTOM_REPORTS = (
    ('Custom Reports', (
        anc_hmis_report.AncHmisReport,
        ld_hmis_report.LdHmisReport,
        immunization_hmis_report.ImmunizationHmisReport,
        all_hmis_report.AllHmisReport,
        project_indicators_report.ProjectIndicatorsReport,
        aggregate_facility_web_hmis_report.AggregateFacilityWebHmisReport,
        mcct_project_review.McctProjectReview,
        mcct_project_review.McctClientApprovalPage,
        mcct_project_review.McctClientPaymentPage,
        mcct_project_review.McctPaidClientsPage,
        mcct_project_review.McctRejectedClientPage,
        mcct_project_review.McctClientLogPage,
        mcct_monthly_aggregate_report.McctMonthlyAggregateReport
    )),
)
