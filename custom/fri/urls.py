from django.conf.urls import *

from custom.fri.views import upload_message_bank

urlpatterns = patterns('custom.fri.views',
    url(r'^upload_message_bank/$', upload_message_bank, name='fri_upload_message_bank'),
)
