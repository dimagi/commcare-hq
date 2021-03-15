from corehq.util.view_utils import absolute_reverse


def resource_url(domain, resource_type, case_id):
    from corehq.motech.fhir.views import get_view
    return absolute_reverse(get_view, args=(domain, resource_type, case_id))
