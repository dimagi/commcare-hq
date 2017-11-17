from __future__ import absolute_import
from django.conf.urls import url

from custom.fri.views import upload_message_bank

urlpatterns = [
    url(r'^upload_message_bank/$', upload_message_bank, name='fri_upload_message_bank'),
]
