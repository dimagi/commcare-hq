from django.contrib import messages
from django.utils.translation import ugettext_lazy as _
from django.utils.decorators import method_decorator

from corehq import toggles
from corehq.apps.hqwebapp.decorators import use_daterangepicker
from custom.icds.forms import CustomSMSReportRequestForm
from corehq.apps.sms.views import BaseMessagingSectionView
from custom.icds.tasks.sms import send_custom_sms_report


@method_decorator(toggles.ICDS_CUSTOM_SMS_REPORT.required_decorator(), name='dispatch')
class SMSUsageReport(BaseMessagingSectionView):
    template_name = 'icds/sms/custom_sms_report.html'
    urlname = 'sms_usage_report'
    page_title = _('Custom SMS Usage Report')

    @use_daterangepicker
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    @property
    def page_context(self):
        self.request_form = CustomSMSReportRequestForm()
        return {
            'request_form': self.request_form,
        }

    def post(self, request, *args, **kwargs):
        self.request_form = CustomSMSReportRequestForm(request.POST)
        user_email = request.user.email
        if not user_email:
            messages.error(self.request, _("Unable to find any email associated with your account"))
            return self.get(*args, **kwargs)
        if self.request_form.is_valid():
            data = self.request_form.cleaned_data
            start_date = data['start_date']
            end_date = data['end_date']
            send_custom_sms_report.delay(start_date, end_date, user_email)
            messages.success(self.request, _(
                "Report will we soon emailed to your email i.e {user_email}"
                .format(user_email=user_email))
            )
        else:
            for message_list in self.request_form.errors.values():
                for message in message_list:
                    messages.error(self.request, message)
        return self.get(*args, **kwargs)
