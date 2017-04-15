from django.conf.urls import url

from custom.rch.views import BeneficariesList, BeneficiaryView

urlpatterns = [
    url(r'^beneficiaries/$', BeneficariesList.as_view(), name=BeneficariesList.urlname),
    url(r'^beneficiary/(?P<beneficiary_id>\d+)/$', BeneficiaryView.as_view(),
        name=BeneficiaryView.urlname),
]
