import json

from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from soil import DownloadBase

from corehq import privileges
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.api.decorators import allow_cors
from corehq.apps.case_importer.views import require_can_edit_data
from corehq.apps.domain.decorators import (
    api_auth,
    require_superuser_or_contractor,
)
from corehq.apps.domain.views.settings import BaseProjectSettingsView
from corehq.apps.hqwebapp.decorators import waf_allow
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.utils import should_use_sql_backend
from corehq.pillows.case_search import domain_needs_search_index
from corehq.toggles import CASE_API_V0_6
from corehq.util.view_utils import reverse

from .api.core import SubmissionError, UserError, serialize_case
from .api.get_list import get_list
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
        if not should_use_sql_backend(domain):
            raise Http404("Domain: {} is not a SQL domain".format(domain))
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
@api_auth
@require_can_edit_data
@CASE_API_V0_6.required_decorator()
@requires_privilege_with_fallback(privileges.API_ACCESS)
def case_api(request, domain, case_id=None):
    if request.method == 'GET' and case_id:
        return _handle_individual_get(request, case_id)
    if request.method == 'GET' and not case_id and domain_needs_search_index(domain):
        return _handle_list_view(request)
    if request.method == 'POST' and not case_id:
        return _handle_case_update(request)
    if request.method == 'PUT' and case_id:
        return _handle_case_update(request, case_id)
    return JsonResponse({'error': "Request method not allowed"}, status=405)


def _handle_individual_get(request, case_id):
    try:
        case = CaseAccessors(request.domain).get_case(case_id)
        if case.domain != request.domain:
            raise CaseNotFound()
    except CaseNotFound:
        return JsonResponse({'error': f"Case '{case_id}' not found"}, status=404)
    return JsonResponse(serialize_case(case))


def _handle_list_view(request):
    try:
        res = get_list(request.domain, request.GET.dict())
    except UserError as e:
        return JsonResponse({'error': str(e)}, status=400)

    if 'next' in res:
        res['next'] = reverse('case_api', args=[request.domain], params=res['next'], absolute=True)
    return JsonResponse(res)


def _handle_case_update(request, case_id=None):
    try:
        data = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({'error': "Payload must be valid JSON"}, status=400)

    try:
        xform, case_or_cases = handle_case_update(
            domain=request.domain,
            data=data,
            user=request.couch_user,
            device_id=request.META.get('HTTP_USER_AGENT'),
            case_id=case_id,
        )
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
