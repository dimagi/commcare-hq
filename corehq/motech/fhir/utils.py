from corehq.apps.consumer_user.models import CaseRelationshipOauthToken
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.view_utils import absolute_reverse


def resource_url(domain, resource_type, case_id):
    from corehq.motech.fhir.views import get_view
    return absolute_reverse(get_view, args=(domain, resource_type, case_id))


def case_access_authorized(domain, access_token, case_id):
    """Case Access is allowed if:
    - There exists a CaseRelationship for this access token
    - There exist a CaseRelationship for any ancestor cases for this access token
    """
    ancestor_case_ids = CaseAccessors(domain).get_indexed_case_ids([case_id])
    return CaseRelationshipOauthToken.objects.filter(
        access_token=access_token,
        consumer_user_case_relationship__case_id__in=[case_id] + ancestor_case_ids
    ).exists()
