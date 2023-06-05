import json
import jsonschema
from django.utils.decorators import method_decorator
from django.urls import reverse

from django.http import HttpResponseRedirect, HttpResponseBadRequest
from django.utils.translation import gettext_lazy as _

from corehq import toggles
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.geospatial.reports import CaseManagementMap
from corehq.util.view_utils import json_error
from .routing_solvers.mapbox_optimize import (
    submit_routing_request,
    routing_status
)

from dimagi.utils.web import json_response


def geospatial_default(request, *args, **kwargs):
    return HttpResponseRedirect(CaseManagementMap.get_url(*args, **kwargs))


class MapboxOptimizationV2(BaseDomainView):
    urlname = 'mapbox_routing'

    def get(self, request):
        return geospatial_default(request)

    @json_error
    def post(self, request):
        # Submits the given request JSON to Mapbox Optimize V2 API
        #   and responds with a result ID that can be polled
        request_json = json.loads(request.body.decode('utf-8'))
        try:
            poll_id = submit_routing_request(request_json)
            return json_response(
                {"poll_url": reverse("mapbox_routing_status", args=[self.domain, poll_id])}
            )
        except jsonschema.exceptions.ValidationError as e:
            return HttpResponseBadRequest(str(e))

    @method_decorator(toggles.GEOSPATIAL.required_decorator())
    def dispatch(self, request, domain, *args, **kwargs):
        self.domain = domain
        return super(MapboxOptimizationV2, self).dispatch(request, *args, **kwargs)


def mapbox_routing_status(request, domain, poll_id):
    return routing_status(poll_id)
