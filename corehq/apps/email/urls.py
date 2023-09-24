from corehq.apps.email.views import EmailSMTPSettingsView, default
from django.conf.urls import re_path as url

urlpatterns = [
    url(r'settings/', EmailSMTPSettingsView.as_view(), name=EmailSMTPSettingsView.urlname),
    url(r'^$', default, name='email_default'),
]
