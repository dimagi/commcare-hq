from django.conf.urls import url

from custom.enikshay.integrations.bets.views import (
    BETSVoucherRepeaterView,
)

urlpatterns = [
    url(
        r'^new_bets_voucher_repeater$',
        BETSVoucherRepeaterView.as_view(),
        {'repeater_type': 'BETSVoucherRepeater'},
        name=BETSVoucherRepeaterView.urlname
    ),
]
