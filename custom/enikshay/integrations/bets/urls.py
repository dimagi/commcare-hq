from django.conf.urls import url
from .views import update_voucher, update_incentive

from custom.enikshay.integrations.bets.views import (
    BETSUserRepeaterView,
    BETSLocationRepeaterView,
)

urlpatterns = [
    url(r'^update_voucher$', update_voucher, name='update_voucher'),
    url(r'^update_incentive$', update_incentive, name='update_incentive'),
    url(
        r'^user_repeater$',
        BETSUserRepeaterView.as_view(),
        {'repeater_type': 'UserRepeater'},
        name=BETSUserRepeaterView.urlname
    ),
    url(
        r'^location_repeater$',
        BETSLocationRepeaterView.as_view(),
        {'repeater_type': 'LocationRepeater'},
        name=BETSLocationRepeaterView.urlname
    ),
]
