from corehq.apps.email.views import EmailSMTPSettingsView
from django.conf.urls import re_path as url

urlpatterns = [
    url(r'settings/', EmailSMTPSettingsView.as_view(), name=EmailSMTPSettingsView.urlname),
]
