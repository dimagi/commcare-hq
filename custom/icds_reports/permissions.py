from functools import wraps

from django.http import HttpResponse

from corehq.apps.locations.permissions import user_can_access_location_id
from custom.icds_reports.utils import icds_pre_release_features


def can_access_location_data(view_fn):
    """
    Decorator controlling a user's access to VIEW data for a specific location.
    """
    @wraps(view_fn)
    def _inner(request, domain, *args, **kwargs):
        def call_view(): return view_fn(request, domain, *args, **kwargs)
        if icds_pre_release_features(request.couch_user):
            loc_id = request.GET.get('location_id')
            def return_no_location_access_response():
                return HttpResponse('No access to the location {} for the logged in user'.format(loc_id),
                                    status=403)
            if not loc_id and not request.couch_user.has_permission(domain, 'access_all_locations'):
                return return_no_location_access_response()
            if loc_id and not user_can_access_location_id(domain, request.couch_user, loc_id):
                return return_no_location_access_response()
        return call_view()
    return _inner
