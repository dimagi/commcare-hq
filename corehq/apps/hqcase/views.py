import json

from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from jsonobject.exceptions import BadValueError

from couchforms.models import XFormError
from soil import DownloadBase

from corehq import privileges
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.domain.decorators import (
    api_auth,
    require_superuser_or_contractor,
)
from corehq.apps.domain.views.settings import BaseProjectSettingsView
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.hqwebapp.decorators import waf_allow
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.utils import should_use_sql_backend

from .api import JsonCaseCreation, JsonCaseUpdate, serialize_case
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


# TODO switch to @require_can_edit_data
@waf_allow('XSS_BODY')
@csrf_exempt
@api_auth
@require_superuser_or_contractor
@requires_privilege_with_fallback(privileges.API_ACCESS)
def case_api(request, domain, case_id=None):
    if request.method == 'POST' and not case_id:
        return _handle_case_update(request)
    if request.method == 'PUT' and case_id:
        return _handle_case_update(request, case_id)
    return JsonResponse({'error': "Request method not allowed"}, status=405)


def _handle_case_update(request, case_id=None):
    try:
        data = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({'error': "Payload must be valid JSON"}, status=400)

    if isinstance(data, list):
        return _bulk_update(request, data)
    else:
        return _create_or_update_case(request, data, case_id)


def _create_or_update_case(request, data, case_id=None):
    if case_id is not None and _missing_cases(request.domain, [case_id]):
        return JsonResponse({'error': f"No case found with ID '{case_id}'"}, status=400)

    try:
        update = _get_case_update(data, request.couch_user.user_id, case_id)
    except BadValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

    xform, cases = _submit_case_updates([update], request)
    if isinstance(xform, XFormError):
        return JsonResponse({
            'error': xform.problem,
            '@form_id': xform.form_id,
        }, status=400)
    return JsonResponse({
        '@form_id': xform.form_id,
        'case': serialize_case(cases[0]),
    })


def _bulk_update(request, all_data):
    if len(all_data) > 100:
        msg = "You cannot submit more than 100 updates in a single request"
        return JsonResponse({'error': msg}, status=400)

    existing_ids = [c['@case_id'] for c in all_data if isinstance(c, dict) and '@case_id' in c]
    missing = _missing_cases(request.domain, existing_ids)
    if missing:
        msg = f"The following case IDs were not found: {', '.join(missing)}"
        return JsonResponse({'error': msg}, status=400)

    updates = []
    errors = []
    for i, data in enumerate(all_data):
        try:
            update = _get_case_update(data, request.couch_user.user_id, data.pop('@case_id', None))
            updates.append(update)
        except BadValueError as e:
            errors.append(f'Error in row {i}: {e}')

    if errors:
        return JsonResponse({'errors': errors}, status=400)

    xform, cases = _submit_case_updates(updates, request)
    if isinstance(xform, XFormError):
        return JsonResponse({
            'error': xform.problem,
            '@form_id': xform.form_id,
        }, status=400)
    return JsonResponse({
        '@form_id': xform.form_id,
        'cases': [serialize_case(case) for case in cases],
    })


def _missing_cases(domain, case_ids):
    return set(case_ids) - {
        case.case_id for case in
        CaseAccessors(domain).get_cases(case_ids)
        if case.domain == domain
    }


def _get_case_update(data, user_id, case_id=None):
    update_class = JsonCaseCreation if case_id is None else JsonCaseUpdate
    additonal_args = {'user_id': user_id}
    if case_id is not None:
        additonal_args['case_id'] = case_id
    return update_class.wrap({**data, **additonal_args})


def _submit_case_updates(updates, request):
    return submit_case_blocks(
        case_blocks=[update.get_caseblock() for update in updates],
        domain=request.domain,
        username=request.couch_user.username,
        user_id=request.couch_user.user_id,
        xmlns='http://commcarehq.org/case_api',
        device_id=request.META.get('HTTP_USER_AGENT'),
    )
