from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.reports.views',
                       url(r'^$', "report_list",
                            name="report_list"),

                       url(r'^user_summary/$', 'user_summary',
                           name='user_summary_report'),
#
#                       url(r'^unrecorded/$', 'unrecorded_referral_list',
#                           name='unrecorded_referral_list'),
#					   url(r'^mortality_register/$', 'mortality_register',
#                           name='mortality_register'),
#                       url(r'^pi/under5/$', 'under_five_pi',
#                           name='under_five_pi'),
#                       url(r'^pi/adult/$', 'adult_pi',
#                           name='adult_pi'),
#                       url(r'^pi/pregnancy/$', 'pregnancy_pi',
#                           name='pregnancy_pi'),
#                       url(r'^pi/chw/$', 'chw_pi',
#                           name='chw_pi'),
#                       url(r'^punchcard/$', 'punchcard',
#                           name='punchcard_report'),
#                       url(r'^entrytime/$', 'entrytime',
#                           name='entrytime_report'),
#                       url(r'^chw_summary/$', 'single_chw_summary',
#                           name='chw_summary_report'),
                       
                        
)
