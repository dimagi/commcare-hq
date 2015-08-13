from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_POST
from corehq import toggles
from corehq.apps.performance_sms import dbaccessors
from corehq.apps.performance_sms.forms import PerformanceMessageEditForm
from corehq.apps.performance_sms.message_sender import send_messages_for_config
from corehq.apps.performance_sms.models import PerformanceConfiguration
from corehq.apps.reminders.views import reminders_framework_permission
from corehq.util import get_document_or_404
from dimagi.utils.logging import notify_exception


@reminders_framework_permission
@toggles.SMS_PERFORMANCE_FEEDBACK.required_decorator()
def list_performance_configs(request, domain):
    return render(request, "performance_sms/list_performance_configs.html", {
        'domain': domain,
        'performance_configs': dbaccessors.by_domain(domain)
    })


@reminders_framework_permission
@toggles.SMS_PERFORMANCE_FEEDBACK.required_decorator()
def add_performance_config(request, domain):
    return _edit_performance_message_shared(request, domain, PerformanceConfiguration(domain=domain))


@reminders_framework_permission
@toggles.SMS_PERFORMANCE_FEEDBACK.required_decorator()
def edit_performance_config(request, domain, config_id):
    config = get_document_or_404(PerformanceConfiguration, domain, config_id)
    return _edit_performance_message_shared(request, domain, config)


def _edit_performance_message_shared(request, domain, config):
    if request.method == 'POST':
        form = PerformanceMessageEditForm(domain, config=config, data=request.POST)
        if form.is_valid():
            messages.success(request, _(u'Performance Message saved!'))
            form.save()
            return HttpResponseRedirect(reverse('performance_sms.list_performance_configs', args=[domain]))
    else:
        form = PerformanceMessageEditForm(domain, config=config)

    return render(request, "performance_sms/edit_performance_config.html", {
        'domain': domain,
        'form': form,
        'editing': bool(config._id),
        'sources_map': form.app_source_helper.all_sources
    })


@reminders_framework_permission
@toggles.SMS_PERFORMANCE_FEEDBACK.required_decorator()
@require_POST
def delete_performance_config(request, domain, config_id):
    config = get_document_or_404(PerformanceConfiguration, domain, config_id)
    config.delete()
    messages.success(request, _(u'Performance Message deleted!'))
    return HttpResponseRedirect(reverse('performance_sms.list_performance_configs', args=[domain]))


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
    return HttpResponseRedirect(reverse('performance_sms.list_performance_configs', args=[domain]))
