from django.contrib import messages
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _

from corehq import toggles
from corehq.apps.hqwebapp.decorators import use_daterangepicker
from corehq.apps.sms.views import BaseMessagingSectionView
from custom.icds.forms import CustomSMSReportRequestForm
from custom.icds.tasks.sms import send_custom_sms_report
from custom.icds_core.const import SMSUsageReport_urlname
from custom.icds.utils.custom_sms_report import CustomSMSReportTracker


@method_decorator(toggles.ICDS_CUSTOM_SMS_REPORT.required_decorator(), name='dispatch')
class SMSUsageReport(BaseMessagingSectionView):
    template_name = 'icds/sms/custom_sms_report.html'
    urlname = SMSUsageReport_urlname
    page_title = _('Custom SMS Usage Report')
    report_tracker = CustomSMSReportTracker()

    @use_daterangepicker
    def dispatch(self, *args, **kwargs):
        messages.info(self.request, _('Please note that this report takes a few hours to process.'))
        return super().dispatch(*args, **kwargs)

    @property
    def page_context(self):
        reports_in_progress = self.report_tracker.active_reports
        report_count = len(reports_in_progress)
        disable_submit = True if report_count >= 3 else False
        if disable_submit:
            messages.info(self.request, 'Only 3 concurrent reports are allowed at a time.')
        if report_count > 0:
            display_message = _prepare_display_message(reports_in_progress, report_count)
            messages.info(self.request, display_message)
        self.request_form = CustomSMSReportRequestForm()
        return {
            'request_form': self.request_form,
            'disable_submit': disable_submit,
        }

    def post(self, request, *args, **kwargs):
        reports_in_progress = self.report_tracker.active_reports
        if len(reports_in_progress) >= 3:
            messages.warning(self.request,
                _("{report_count} are currently in progress. Please wait for them to finish")
                .format(report_count=len(reports_in_progress)))
            return self.get(*args, **kwargs)
        self.request_form = CustomSMSReportRequestForm(request.POST)
        user_email = request.user.email
        if not user_email:
            messages.error(self.request, _("Unable to find any email associated with your account"))
            return self.get(*args, **kwargs)
        if self.request_form.is_valid():
            data = self.request_form.cleaned_data
            start_date = data['start_date']
            end_date = data['end_date']
            if(_report_already_in_progress(reports_in_progress, start_date, end_date)):
                messages.warning(
                    self.request,
                    _("Report for duration {start_date}-{end_date} already in progress").format(
                        start_date=start_date,
                        end_date=end_date,
                    ))
                return self.get(*args, **kwargs)
            send_custom_sms_report.delay(str(start_date), str(end_date), user_email)
            messages.success(self.request, _(
                "Report will we soon emailed to your email i.e {user_email}"
                .format(user_email=user_email))
            )
        else:
            for message_list in self.request_form.errors.values():
                for message in message_list:
                    messages.error(self.request, message)
        return self.get(*args, **kwargs)


def _prepare_display_message(reports_in_progress, report_count):
    message = _('Currently {reports_count} {report_text} for duration\n').format(
        reports_count=report_count,
        report_text='reports' if report_count > 1 else 'report',
    )
    for index, report in enumerate(reports_in_progress):
        message += _('{start_date} to {end_date}').format(
            start_date=report['start_date'],
            end_date=report['end_date']
        )
        if index != report_count - 1:
            message += ', '
    message += _(' {is_or_are} in progress').format(
        is_or_are='are' if report_count > 1 else 'is',
    )
    return message


def _report_already_in_progress(reports, start_date, end_date):
    similar_reports = [report for report in reports
        if report['start_date'] == str(start_date) and report['end_date'] == str(end_date)]
    return len(similar_reports) >= 1
