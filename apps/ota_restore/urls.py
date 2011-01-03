from django.conf.urls.defaults import *


urlpatterns = patterns('',         
    #this ota_restore code is from cchq 0.9. todo: upgrade to 1.0 casexml processing              
    #url(r'^ota_restore/?$', 'ota_restore.views.ota_restore'),
    (r'^digest_test/?$', 'ota_restore.views.digest_test'),

)
