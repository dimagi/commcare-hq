from django.conf.urls import url

from custom.rch.views import BeneficiaryView

urlpatterns = [
    url(r'^beneficiary/(?P<beneficiary_id>\d+)/$', BeneficiaryView.as_view(),
        name=BeneficiaryView.urlname),
]
