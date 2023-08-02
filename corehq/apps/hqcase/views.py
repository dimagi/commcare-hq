import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from django.core.exceptions import PermissionDenied

from soil import DownloadBase

from corehq import privileges
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.api.decorators import allow_cors, api_throttle
from corehq.apps.domain.decorators import (
    api_auth,
    require_superuser_or_contractor,
)
from corehq.apps.domain.views.settings import BaseProjectSettingsView
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.hqwebapp.decorators import waf_allow
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions
from corehq.toggles import CASE_API_V0_6
from corehq.util.es.elasticsearch import NotFoundError
from corehq.util.view_utils import reverse
from corehq.apps.locations.permissions import user_can_access_case
from corehq.apps.locations.permissions import location_safe

from .api.core import SubmissionError, UserError, serialize_case, serialize_es_case
from .api.get_list import get_list
from .api.get_bulk import get_bulk
from .api.updates import handle_case_update
from .tasks import delete_exploded_case_task, explode_case_task


class ExplodeCasesView(BaseProjectSettingsView, TemplateView):
    url_name = "explode_cases"
    template_name = "hqcase/explode_cases.html"
    page_title = "Explode Cases"

    @method_decorator(require_superuser_or_contractor)
    def dispatch(self, *args, **kwargs):
        return super(ExplodeCasesView, self).dispatch(*args, **kwargs)

    def get(self, request, domain):
        return super(ExplodeCasesView, self).get(request, domain)

    def get_context_data(self, **kwargs):
        context = super(ExplodeCasesView, self).get_context_data(**kwargs)
        context.update({
            'domain': self.domain,
        })
        return context

    def post(self, request, domain):
        if 'explosion_id' in request.POST:
            return self.delete_cases(request, domain)
        else:
            return self.explode_cases(request, domain)

    def explode_cases(self, request, domain):
        user_id = request.POST.get('user_id')
        factor = request.POST.get('factor', '2')
        try:
            factor = int(factor)
        except ValueError:
            messages.error(request, 'factor must be an int; was: %s' % factor)
        else:
            download = DownloadBase()
            res = explode_case_task.delay(self.domain, user_id, factor)
            download.set_task(res)

            return redirect('hq_soil_download', self.domain, download.download_id)

    def delete_cases(self, request, domain):
        explosion_id = request.POST.get('explosion_id')
        download = DownloadBase()
        res = delete_exploded_case_task.delay(self.domain, explosion_id)
        download.set_task(res)
        return redirect('hq_soil_download', self.domain, download.download_id)


@waf_allow('XSS_BODY')
@csrf_exempt
@allow_cors(['OPTIONS', 'GET', 'POST', 'PUT'])
@api_auth(allow_creds_in_data=False)
@require_permission(HqPermissions.edit_data)
@require_permission(HqPermissions.access_api)
@CASE_API_V0_6.required_decorator()
@requires_privilege_with_fallback(privileges.API_ACCESS)
@api_throttle
@location_safe
def case_api(request, domain, case_id=None):
    if request.method == 'GET' and case_id:
        return _handle_get(request, case_id)
    if request.method == 'GET' and not case_id:
        return _handle_list_view(request)
    if request.method == 'POST' and not case_id:
        return _handle_case_update(request, is_creation=True)
    if request.method == 'PUT':
        return _handle_case_update(request, is_creation=False, case_id=case_id)
    return JsonResponse({'error': "Request method not allowed"}, status=405)


@waf_allow('XSS_BODY')
@csrf_exempt
@allow_cors(['OPTIONS', 'GET', 'POST'])
@api_auth(allow_creds_in_data=False)
@require_permission(HqPermissions.edit_data)
@require_permission(HqPermissions.access_api)
@CASE_API_V0_6.required_decorator()
@requires_privilege_with_fallback(privileges.API_ACCESS)
@api_throttle
def case_api_bulk_fetch(request, domain):
    return _handle_bulk_fetch(request)


def _handle_get(request, case_id):
    if ',' in case_id:
        return _get_bulk_cases(request, case_ids=case_id.split(','))
    return _get_single_case(request, case_id)


def _get_bulk_cases(request, case_ids=None, external_ids=None):
    try:
        res = get_bulk(request.domain, request.couch_user, case_ids, external_ids)
    except UserError as e:
        return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse(res)


def _get_single_case(request, case_id):
    try:
        case = case_search_adapter.get(case_id)
        if case['domain'] != request.domain:
            raise NotFoundError()
        if not user_can_access_case(request.domain, request.couch_user, case, es_case=True):
            raise PermissionDenied()
    except NotFoundError:
        return JsonResponse({'error': f"Case '{case_id}' not found"}, status=404)
    except PermissionDenied:
        return JsonResponse({'error': f"Insufficent permission for Case '{case_id}'"}, status=403)
    return JsonResponse(serialize_es_case(case))


def _handle_bulk_fetch(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({'error': "Payload must be valid JSON"}, status=400)

    case_ids = data.get('case_ids')
    external_ids = data.get('external_ids')
    if not case_ids and not external_ids:
        return JsonResponse({'error': "Payload must include 'case_ids' or 'external_ids' fields"}, status=400)

    return _get_bulk_cases(request, case_ids=case_ids, external_ids=external_ids)


def _handle_list_view(request):
    try:
        res = get_list(request.domain, request.couch_user, request.GET)
    except UserError as e:
        return JsonResponse({'error': str(e)}, status=400)

    if 'next' in res:
        res['next'] = reverse('case_api', args=[request.domain], params=res['next'], absolute=True)
    return JsonResponse(res)


def _handle_case_update(request, is_creation, case_id=None):
    try:
        data = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({'error': "Payload must be valid JSON"}, status=400)

    if not is_creation and case_id and 'case_id' not in data:
        data['case_id'] = case_id

    try:
        xform, case_or_cases = handle_case_update(
            domain=request.domain,
            data=data,
            user=request.couch_user,
            device_id=request.META.get('HTTP_USER_AGENT'),
            is_creation=is_creation,
        )
    except PermissionDenied as e:
        return JsonResponse({'error': str(e)}, status=403)
    except UserError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except SubmissionError as e:
        return JsonResponse({
            'error': str(e),
            'form_id': e.form_id,
        }, status=400)

    if isinstance(case_or_cases, list):
        return JsonResponse({
            'form_id': xform.form_id,
            'cases': [serialize_case(case) for case in case_or_cases],
        })
    return JsonResponse({
        'form_id': xform.form_id,
        'case': serialize_case(case_or_cases),
    })
