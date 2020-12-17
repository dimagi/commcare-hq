import json

from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from jsonobject.exceptions import BadValueError

from soil import DownloadBase

from corehq.apps.domain.decorators import (
    api_auth,
    require_superuser_or_contractor,
)
from corehq.apps.domain.views.settings import BaseProjectSettingsView
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.hqwebapp.decorators import waf_allow
from corehq.form_processor.utils import should_use_sql_backend

from .api import JsonCaseCreation, JsonCaseUpdate
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
@require_POST
@api_auth
@require_superuser_or_contractor
def case_api(request, domain, case_id=None):
    try:
        data = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({'error': "Payload must be valid JSON"}, status=400)

    update_class = JsonCaseCreation if case_id is None else JsonCaseUpdate
    additonal_args = {'user_id': request.couch_user.user_id}
    if case_id is not None:
        additonal_args['case_id'] = case_id
    try:
        update = update_class.wrap({**data, **additonal_args})
    except BadValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

    xform, cases = submit_case_blocks(
        case_blocks=[update.get_caseblock()],
        domain=domain,
        username=request.couch_user.username,
        user_id=request.couch_user.user_id,
        xmlns='http://commcarehq.org/case_api',
        device_id=request.META.get('HTTP_USER_AGENT'),
    )
    return JsonResponse({
        '@form_id': xform.form_id,
        '@case_id': cases[0].case_id,
    })
