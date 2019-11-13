import json
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from couchdbkit import ResourceNotFound
from memoized import memoized
from six.moves.urllib.parse import urlencode

from dimagi.utils.couch import CriticalSection
from dimagi.utils.couch.database import apply_update
from dimagi.utils.couch.resource_conflict import retry_resource
from dimagi.utils.logging import notify_exception
from dimagi.utils.name_to_url import name_to_url

from corehq.apps.accounting.models import SubscriptionAdjustmentMethod
from corehq.apps.accounting.tasks import ensure_explicit_community_subscription
from corehq.apps.app_manager.views.apps import clear_app_cache
from corehq.apps.appstore.exceptions import CopiedFromDeletedException
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.domain.exceptions import NameUnavailableException
from corehq.apps.domain.models import Domain
from corehq.apps.fixtures.models import FixtureDataType
from corehq.apps.hqwebapp.views import BaseSectionPageView
from corehq.apps.userreports.exceptions import ReportConfigurationNotFoundError
from corehq.elastic import (
    es_query,
    fill_mapping_with_facets,
    parse_args_for_es,
)

def rewrite_url(request, path):
    return HttpResponseRedirect('/exchange%s?%s' % (path, request.META['QUERY_STRING']))


@require_superuser
def approve_app(request, snapshot):
    domain_obj = Domain.get(snapshot)
    if request.GET.get('approve') == 'true':
        domain_obj.is_approved = True
        domain_obj.save()
    elif request.GET.get('approve') == 'false':
        domain_obj.is_approved = False
        domain_obj.save()
    return HttpResponseRedirect(request.META.get('HTTP_REFERER') or reverse('appstore'))


def project_image(request, snapshot):
    project = Domain.get(snapshot)
    if project.image_path:
        image = project.fetch_attachment(project.image_path)
        return HttpResponse(image, content_type=project.image_type)
    else:
        raise Http404()


def project_documentation_file(request, snapshot):
    project = Domain.get(snapshot)
    if project.documentation_file_path:
        documentation_file = project.fetch_attachment(project.documentation_file_path)
        return HttpResponse(documentation_file, content_type=project.documentation_file_type)
    else:
        raise Http404()
