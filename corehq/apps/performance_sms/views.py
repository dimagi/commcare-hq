from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils.translation import ugettext as _
from corehq import toggles
from corehq.apps.performance_sms import dbaccessors
from corehq.apps.performance_sms.forms import PerformanceMessageEditForm
from corehq.apps.performance_sms.models import PerformanceConfiguration
from corehq.apps.reminders.views import reminders_framework_permission


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


def _edit_performance_message_shared(request, domain, config):
    if request.method == 'POST':
        form = PerformanceMessageEditForm(domain, data=request.POST)
        if form.is_valid():
            print form.cleaned_data

            messages.success(request, _(u'Performance Message saved!'))
            # return HttpResponseRedirect(reverse('performance_sms.list_performance_configs', args=[domain]))
    else:
        form = PerformanceMessageEditForm(domain)

    return render(request, "performance_sms/add_performance_config.html", {
        'domain': domain,
        'form': form,
        'sources_map': form.app_source_helper.all_sources
    })
