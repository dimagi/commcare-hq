from corehq.apps.email.views import EmailSMTPSettingsView
from django.conf.urls import re_path as url

from corehq.messaging.scheduling.views import MessagingDashboardView

urlpatterns = [
    url(r'settings/', EmailSMTPSettingsView.as_view(), name=EmailSMTPSettingsView.urlname),
    url(r'^$', MessagingDashboardView.as_view(), name=MessagingDashboardView.urlname),
]
