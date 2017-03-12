from django.conf.urls import url

from custom.rch.views import (
    BeneficariesList,
    MotherBeneficiaryView,
    ChildBeneficiaryView,
    MotherFieldMappingCreateView,
    ChildFieldMappingCreateView,
    ChildFieldMappingUpdateView,
    MotherFieldMappingUpdateView,
    MotherFieldMappingDeleteView,
    ChildFieldMappingDeleteView,
)

urlpatterns = [
    url(r'^beneficiaries/$', BeneficariesList.as_view(), name=BeneficariesList.urlname),
    url(r'^beneficiary/mother/(?P<beneficiary_id>\d+)/$', MotherBeneficiaryView.as_view(),
        name=MotherBeneficiaryView.urlname),
    url(r'^beneficiary/child/(?P<beneficiary_id>\d+)/$', ChildBeneficiaryView.as_view(),
        name=ChildBeneficiaryView.urlname),
    url(r'^beneficiary/mother/field_mappings/$', MotherFieldMappingCreateView.as_view(),
        name=MotherFieldMappingCreateView.urlname),
    url(r'^beneficiary/child/field_mappings/$', ChildFieldMappingCreateView.as_view(),
        name=ChildFieldMappingCreateView.urlname),
    url(r'^beneficiary/mother/field_mappings/(?P<pk>\d+)$', MotherFieldMappingUpdateView.as_view(),
        name=MotherFieldMappingUpdateView.urlname),
    url(r'^beneficiary/child/field_mappings/(?P<pk>\d+)$', ChildFieldMappingUpdateView.as_view(),
        name=ChildFieldMappingUpdateView.urlname),
    url(r'^beneficiary/mother/field_mappings/delete/(?P<pk>\d+)$', MotherFieldMappingDeleteView.as_view(),
        name=MotherFieldMappingDeleteView.urlname),
    url(r'^beneficiary/child/field_mappings/delete/(?P<pk>\d+)$', ChildFieldMappingDeleteView.as_view(),
        name=ChildFieldMappingDeleteView.urlname),
]
