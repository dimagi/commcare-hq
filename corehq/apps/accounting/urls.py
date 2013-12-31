from django.conf.urls.defaults import *


urlpatterns = patterns('corehq.apps.accounting.views',
    url(r'view_billing_accounts', 'view_billing_accounts', name='view_billing_accounts'),
)
