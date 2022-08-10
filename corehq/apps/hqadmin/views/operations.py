from django.contrib import messages
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from memoized import memoized

from corehq.apps.domain.decorators import (
    require_superuser,
    require_superuser_or_contractor,
)
from corehq.apps.hqadmin.forms import (
    EmailForm,
    ReprocessMessagingCaseUpdatesForm,
)
from corehq.apps.hqadmin.tasks import send_mass_emails
from corehq.apps.hqadmin.views.utils import (
    BaseAdminSectionView,
    get_hqadmin_base_context,
)
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.models import CommCareCase
from corehq.messaging.tasks import sync_case_for_messaging_task


@require_superuser_or_contractor
def mass_email(request):
    if request.method == "POST":
        form = EmailForm(request.POST)
        if form.is_valid():
            subject = form.cleaned_data['email_subject']
            html = form.cleaned_data['email_body_html']
            text = form.cleaned_data['email_body_text']
            real_email = form.cleaned_data['real_email']
            send_mass_emails.delay(request.couch_user.get_email(), real_email, subject, html, text)
            messages.success(request, 'Task started. You will receive an email summarizing the results.')
        else:
            messages.error(request, 'Something went wrong, see below.')
    else:
        form = EmailForm()

    context = get_hqadmin_base_context(request)
    context['hide_filters'] = True
    context['form'] = form
    return render(request, "hqadmin/mass_email.html", context)


class CallcenterUCRCheck(BaseAdminSectionView):
    urlname = 'callcenter_ucr_check'
    page_title = gettext_lazy("Check Callcenter UCR tables")
    template_name = "hqadmin/call_center_ucr_check.html"

    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(CallcenterUCRCheck, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        from corehq.apps.callcenter.data_source import get_call_center_domains
        from corehq.apps.callcenter.checks import get_call_center_data_source_stats

        if 'domain' not in self.request.GET:
            return {}

        domain = self.request.GET.get('domain', None)
        if domain:
            domains = [domain]
        else:
            domains = [dom.name for dom in get_call_center_domains() if dom.use_fixtures]

        domain_stats = get_call_center_data_source_stats(domains)

        context = {
            'data': sorted(list(domain_stats.values()), key=lambda s: s.name),
            'domain': domain
        }

        return context


class ReprocessMessagingCaseUpdatesView(BaseAdminSectionView):
    urlname = 'reprocess_messaging_case_updates'
    page_title = gettext_lazy("Reprocess Messaging Case Updates")
    template_name = 'hqadmin/messaging_case_updates.html'

    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(ReprocessMessagingCaseUpdatesView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def form(self):
        if self.request.method == 'POST':
            return ReprocessMessagingCaseUpdatesForm(self.request.POST)
        return ReprocessMessagingCaseUpdatesForm()

    @property
    def page_context(self):
        context = get_hqadmin_base_context(self.request)
        context.update({
            'form': self.form,
        })
        return context

    def get_case(self, case_id):
        try:
            return CommCareCase.objects.get_case(case_id)
        except CaseNotFound:
            return None

    def post(self, request, *args, **kwargs):
        if self.form.is_valid():
            case_ids = self.form.cleaned_data['case_ids']
            case_ids_not_processed = []
            case_ids_processed = []
            for case_id in case_ids:
                case = self.get_case(case_id)
                if not case or case.doc_type != 'CommCareCase':
                    case_ids_not_processed.append(case_id)
                else:
                    sync_case_for_messaging_task.delay(case.domain, case_id)
                    case_ids_processed.append(case_id)

            if case_ids_processed:
                messages.success(self.request,
                    _("Processed the following case ids: {}").format(','.join(case_ids_processed)))

            if case_ids_not_processed:
                messages.error(self.request,
                    _("Could not find cases belonging to these case ids: {}")
                    .format(','.join(case_ids_not_processed)))

        return self.get(request, *args, **kwargs)
