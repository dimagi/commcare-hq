from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, ugettext_lazy
from django.views.decorators.http import require_POST
from corehq import toggles
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.performance_sms import dbaccessors
from corehq.apps.performance_sms.forms import PerformanceMessageEditForm
from corehq.apps.performance_sms.message_sender import send_messages_for_config
from corehq.apps.performance_sms.models import PerformanceConfiguration
from corehq.apps.reminders.views import reminders_framework_permission
from corehq.util import get_document_or_404
from dimagi.utils.decorators.memoized import memoized


class BasePerformanceSMSView(BaseDomainView):
    section_name = ugettext_lazy('Performance Messaging')

    @method_decorator(reminders_framework_permission)
    @method_decorator(toggles.SMS_PERFORMANCE_FEEDBACK.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super(BasePerformanceSMSView, self).dispatch(request, *args, **kwargs)

    @property
    def section_url(self):
        return reverse(ListPerformanceConfigsView.urlname, args=(self.domain, ))


class ListPerformanceConfigsView(BasePerformanceSMSView):
    page_title = ugettext_lazy('Performance Messages')
    urlname = 'performance_sms.list_performance_configs'
    template_name = 'performance_sms/list_performance_configs.html'

    @property
    def page_context(self):
        return {
            'performance_configs': dbaccessors.by_domain(self.domain),
        }


class BasePerformanceConfigView(BasePerformanceSMSView):
    template_name = 'performance_sms/edit_performance_config.html'

    @property
    def performance_config(self):
        return NotImplementedError("must return PerformanceConfiguration")

    @property
    @memoized
    def performance_sms_form(self):
        if self.request.method == 'POST':
            return PerformanceMessageEditForm(
                self.domain,
                config=self.performance_config,
                data=self.request.POST
            )
        return PerformanceMessageEditForm(
            self.domain, config=self.performance_config
        )

    def post(self, request, *args, **kwargs):
        if self.performance_sms_form.is_valid():
            messages.success(self.request, _(u'Performance Message saved!'))
            self.performance_sms_form.save()
            return HttpResponseRedirect(reverse(
                ListPerformanceConfigsView.urlname, args=(self.domain,)))
        return self.get(request, *args, **kwargs)

    @property
    def config_id(self):
        return self.kwargs.get('config_id')

    def page_url(self):
        if self.config_id:
            return reverse(self.urlname, args=(self.domain, self.config_id,))
        return super(BasePerformanceConfigView, self).page_url

    @property
    def page_context(self):
        return {
            'form': self.performance_sms_form,
            'editing': bool(self.performance_config._id),
            'sources_map': self.performance_sms_form.app_source_helper.all_sources,
        }


class AddPerformanceConfigView(BasePerformanceConfigView):
    urlname = 'performance_sms.add_performance_config'
    page_title = ugettext_lazy("New Performance Message")

    @property
    @memoized
    def performance_config(self):
        return PerformanceConfiguration(domain=self.domain)


class EditPerformanceConfig(BasePerformanceConfigView):
    urlname = 'performance_sms.edit_performance_config'
    page_title = ugettext_lazy("Edit Performance Message")

    @property
    @memoized
    def performance_config(self):
        return get_document_or_404(
            PerformanceConfiguration, self.domain, self.config_id
        )


@reminders_framework_permission
@toggles.SMS_PERFORMANCE_FEEDBACK.required_decorator()
@require_POST
def delete_performance_config(request, domain, config_id):
    config = get_document_or_404(PerformanceConfiguration, domain, config_id)
    config.delete()
    messages.success(request, _(u'Performance Message deleted!'))
    return HttpResponseRedirect(reverse(
        ListPerformanceConfigsView.urlname, args=[domain]))


@reminders_framework_permission
@toggles.SMS_PERFORMANCE_FEEDBACK.required_decorator()
def sample_performance_messages(request, domain, config_id):
    return _send_test_messages(request, domain, config_id, actually=False)


@reminders_framework_permission
@toggles.SMS_PERFORMANCE_FEEDBACK.required_decorator()
@require_POST
def send_performance_messages(request, domain, config_id):
    return _send_test_messages(request, domain, config_id, actually=True)


def _send_test_messages(request, domain, config_id, actually):
    performance_config = PerformanceConfiguration.get(config_id)
    assert performance_config.domain == domain
    sent_messages = send_messages_for_config(performance_config, actually_send=actually)
    heading = (
        _('The following messages have been sent') if actually else
        _('Would send the following messages')
    )
    if sent_messages:
        messages.success(
            request,
            mark_safe(_(u"{}: <br>{}").format(
                heading,
                '<br>'.join([
                    u' - {} (to {} via {})'.format(
                        result.message, result.user.raw_username, result.user.phone_number
                    )
                    for result in sent_messages
                ])
            )),
            extra_tags='html'
        )
    else:
        messages.info(request, _('Unfortunately, here were no valid recipients for this message.'))
    return HttpResponseRedirect(reverse(
        ListPerformanceConfigsView.urlname, args=[domain]))
