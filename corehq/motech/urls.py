from django.urls import re_path as url

from corehq.motech.dhis2.views import (
    AddDhis2EntityRepeaterView,
    AddDhis2RepeaterView,
    EditDhis2EntityRepeaterView,
    EditDhis2RepeaterView,
    config_dhis2_entity_repeater,
    config_dhis2_repeater,
)
from corehq.motech.fhir.views import AddFHIRRepeaterView, EditFHIRRepeaterView
from corehq.motech.generic_inbound.reports import ApiLogDetailView
from corehq.motech.generic_inbound.views import (
    ConfigurableAPIEditView,
    ConfigurableAPIListView,
    retry_api_request,
    revert_api_request,
)
from corehq.motech.openmrs.views import (
    AddOpenmrsRepeaterView,
    EditOpenmrsRepeaterView,
    config_openmrs_repeater,
)
from corehq.motech.repeaters.expression.views import (
    AddCaseExpressionRepeaterView,
    EditCaseExpressionRepeaterView,
)
from corehq.motech.repeaters.views import (
    AddCaseRepeaterView,
    AddFormRepeaterView,
    AddRepeaterView,
    DomainForwardingOptionsView,
    EditCaseRepeaterView,
    EditFormRepeaterView,
    EditRepeaterView,
    drop_repeater,
    pause_repeater,
    resume_repeater,
)
from corehq.motech.repeaters.views.repeaters import EditDataRegistryCaseUpdateRepeater, EditReferCaseRepeaterView
from corehq.motech.views import (
    ConnectionSettingsDetailView,
    ConnectionSettingsListView,
    MotechLogDetailView,
    MotechLogListView,
    motech_log_export_view,
    test_connection_settings,
)

urlpatterns = [
    url(r'^conn/$', ConnectionSettingsListView.as_view(),
        name=ConnectionSettingsListView.urlname),
    url(r'^conn/(?P<pk>\d+)/$', ConnectionSettingsDetailView.as_view(),
        name=ConnectionSettingsDetailView.urlname),
    url(r'^conn/add/$', ConnectionSettingsDetailView.as_view(),
        name=ConnectionSettingsDetailView.urlname),
    url(r'^conn/test/$', test_connection_settings,
        name='test_connection_settings'),

    url(r'^forwarding/$', DomainForwardingOptionsView.as_view(), name=DomainForwardingOptionsView.urlname),
    url(r'^forwarding/new/FormRepeater/$', AddFormRepeaterView.as_view(),
        {'repeater_type': 'FormRepeater'}, name=AddFormRepeaterView.urlname),
    url(r'^forwarding/new/CaseRepeater/$', AddCaseRepeaterView.as_view(),
        {'repeater_type': 'CaseRepeater'}, name=AddCaseRepeaterView.urlname),
    url(r'^forwarding/new/OpenmrsRepeater/$', AddOpenmrsRepeaterView.as_view(),
        {'repeater_type': 'OpenmrsRepeater'}, name=AddOpenmrsRepeaterView.urlname),
    url(r'^forwarding/new/Dhis2Repeater/$', AddDhis2RepeaterView.as_view(),
        {'repeater_type': 'Dhis2Repeater'}, name=AddDhis2RepeaterView.urlname),
    url(r'^forwarding/new/Dhis2EntityRepeater/$', AddDhis2EntityRepeaterView.as_view(),
        {'repeater_type': 'Dhis2EntityRepeater'}, name=AddDhis2EntityRepeaterView.urlname),
    url(r'^forwarding/new/FHIRRepeater/$', AddFHIRRepeaterView.as_view(),
        {'repeater_type': 'FHIRRepeater'}, name=AddFHIRRepeaterView.urlname),
    url(r'^forwarding/new/SearchByParamsRepeater/$', AddCaseRepeaterView.as_view(),
        {'repeater_type': 'SearchByParamsRepeater'}, name=AddCaseRepeaterView.urlname),
    url(r'^forwarding/new/ReferCaseRepeater/$', AddCaseRepeaterView.as_view(),
        {'repeater_type': 'ReferCaseRepeater'}, name=AddCaseRepeaterView.urlname),
    url(r'^forwarding/new/DataRegistryCaseUpdateRepeater/$', AddCaseRepeaterView.as_view(),
        {'repeater_type': 'DataRegistryCaseUpdateRepeater'}, name=AddCaseRepeaterView.urlname),
    url(r'^forwarding/new/CaseExpressionRepeater/$', AddCaseExpressionRepeaterView.as_view(),
        {'repeater_type': 'CaseExpressionRepeater'}, name=AddCaseExpressionRepeaterView.urlname),
    url(r'^forwarding/new/(?P<repeater_type>\w+)/$', AddRepeaterView.as_view(), name=AddRepeaterView.urlname),

    url(r'^forwarding/edit/CaseRepeater/(?P<repeater_id>\w+)/$', EditCaseRepeaterView.as_view(),
        {'repeater_type': 'CaseRepeater'}, name=EditCaseRepeaterView.urlname),
    url(r'^forwarding/edit/FormRepeater/(?P<repeater_id>\w+)/$', EditFormRepeaterView.as_view(),
        {'repeater_type': 'FormRepeater'}, name=EditFormRepeaterView.urlname),
    url(r'^forwarding/edit/ReferCaseRepeater/(?P<repeater_id>\w+)/$', EditReferCaseRepeaterView.as_view(),
        {'repeater_type': 'ReferCaseRepeater'}, name=EditReferCaseRepeaterView.urlname),
    url(
        r'^forwarding/edit/DataRegistryCaseUpdateRepeater/(?P<repeater_id>\w+)/$',
        EditDataRegistryCaseUpdateRepeater.as_view(),
        {'repeater_type': 'DataRegistryCaseUpdateRepeater'}, name=EditDataRegistryCaseUpdateRepeater.urlname
    ),
    url(r'^forwarding/edit/OpenmrsRepeater/(?P<repeater_id>\w+)/$', EditOpenmrsRepeaterView.as_view(),
        {'repeater_type': 'OpenmrsRepeater'}, name=EditOpenmrsRepeaterView.urlname),
    url(r'^forwarding/edit/Dhis2Repeater/(?P<repeater_id>\w+)/$', EditDhis2RepeaterView.as_view(),
        {'repeater_type': 'Dhis2Repeater'}, name=EditDhis2RepeaterView.urlname),
    url(r'^forwarding/edit/Dhis2EntityRepeater/(?P<repeater_id>\w+)/$', EditDhis2EntityRepeaterView.as_view(),
        {'repeater_type': 'Dhis2EntityRepeater'}, name=EditDhis2EntityRepeaterView.urlname),
    url(r'^forwarding/edit/FHIRRepeater/(?P<repeater_id>\w+)/$', EditFHIRRepeaterView.as_view(),
        {'repeater_type': 'FHIRRepeater'}, name=EditFHIRRepeaterView.urlname),
    url(
        r'^forwarding/edit/CaseExpressionRepeater/(?P<repeater_id>\w+)/$',
        EditCaseExpressionRepeaterView.as_view(),
        {'repeater_type': 'CaseExpressionRepeater'},
        name=EditCaseExpressionRepeaterView.urlname
    ),
    url(r'^forwarding/edit/(?P<repeater_type>\w+)/(?P<repeater_id>\w+)/$', EditRepeaterView.as_view(),
        name=EditRepeaterView.urlname),

    url(r'^forwarding/config/OpenmrsRepeater/(?P<repeater_id>\w+)/$', config_openmrs_repeater,
        name='config_openmrs_repeater'),
    url(r'^forwarding/config/Dhis2Repeater/(?P<repeater_id>\w+)/$', config_dhis2_repeater,
        name='config_dhis2_repeater'),
    url(r'^forwarding/config/Dhis2EntityRepeater/(?P<repeater_id>\w+)/$', config_dhis2_entity_repeater,
        name='config_dhis2_entity_repeater'),
    url(r'^forwarding/config/(?P<repeater_type>\w+)/(?P<repeater_id>\w+)/$', lambda: None,
        name='config_repeater'),

    url(r'^forwarding/drop/(?P<repeater_id>[\w-]+)/$', drop_repeater, name='drop_repeater'),
    url(r'^forwarding/pause/(?P<repeater_id>[\w-]+)/$', pause_repeater, name='pause_repeater'),
    url(r'^forwarding/resume/(?P<repeater_id>[\w-]+)/$', resume_repeater, name='resume_repeater'),

    url(r'^logs/$', MotechLogListView.as_view(), name=MotechLogListView.urlname),
    url(r'^logs/(?P<pk>\d+)/$', MotechLogDetailView.as_view(), name=MotechLogDetailView.urlname),
    url(r'^logs/remote_api_logs.csv$', motech_log_export_view,
        name='motech_log_export_view'),

    # Generic inbound
    url(r'^inbound/$', ConfigurableAPIListView.as_view(), name=ConfigurableAPIListView.urlname),
    url(r'^inbound/(?P<api_id>\d+)/$', ConfigurableAPIEditView.as_view(), name=ConfigurableAPIEditView.urlname),
    url(r'^inbound/log/(?P<log_id>[\w-]+)/$', ApiLogDetailView.as_view(), name=ApiLogDetailView.urlname),
    url(r'^inbound/revert/(?P<log_id>[\w-]+)/$', revert_api_request, name='revert_api_request'),
    url(r'^inbound/retry/(?P<log_id>[\w-]+)/$', retry_api_request, name='retry_api_request'),
]
