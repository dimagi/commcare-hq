from django.conf.urls import *

urlpatterns = patterns('custom.fri.views',
    url(r'^upload_message_bank/$', 'upload_message_bank', name='fri_upload_message_bank'),
)
