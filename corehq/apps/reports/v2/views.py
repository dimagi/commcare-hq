from __future__ import absolute_import
from __future__ import unicode_literals

import json

from django.http import HttpResponse, Http404
from django.views.decorators.http import require_POST

from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.reports.v2.reports import get_report


@login_and_domain_required
@require_POST
def endpoint_data(request, domain, report_slug, endpoint_slug):

    report_config = get_report(request, domain, report_slug)
    if not report_config.has_permission:
        raise Http404()
    endpoint = report_config.get_data_endpoint(endpoint_slug)

    return HttpResponse(
        json.dumps(report_config.get_data_response(endpoint)),
        content_type="application/json"
    )


@login_and_domain_required
@require_POST
def endpoint_options(request, domain, report_slug, endpoint_slug):

    report_config = get_report(request, domain, report_slug)
    if not report_config.has_permission:
        raise Http404()
    endpoint = report_config.get_options_endpoint(endpoint_slug)

    return HttpResponse(
        json.dumps(endpoint.get_response()),
        content_type="application/json"
    )
