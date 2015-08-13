from django.shortcuts import render
from corehq import toggles
from corehq.apps.performance_sms import dbaccessors
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
    return render(request, "performance_sms/list_performance_configs.html", {
        'domain': domain,
        'performance_configs': dbaccessors.by_domain(domain)
    })



