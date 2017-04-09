from django.conf.urls import url

from custom.rch.views import BeneficariesList, MotherBeneficiaryView, ChildBeneficiaryView

urlpatterns = [
    url(r'^beneficiaries/$', BeneficariesList.as_view(), name=BeneficariesList.urlname),
    url(r'^beneficiary/mother/(?P<beneficiary_id>\d+)/$', MotherBeneficiaryView.as_view(),
        name=MotherBeneficiaryView.urlname),
    url(r'^beneficiary/child/(?P<beneficiary_id>\d+)/$', ChildBeneficiaryView.as_view(),
        name=ChildBeneficiaryView.urlname)
]
