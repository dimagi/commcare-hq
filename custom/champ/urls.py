from __future__ import absolute_import
from django.conf.urls import url

from custom.champ.views import PrevisionVsAchievementsView, DistrictFilterPrevView, \
    CBOFilterView

urlpatterns = [
    url(r'^champ_pva/', PrevisionVsAchievementsView.as_view(), name='champ_pva'),
    url(r'^district_filter/', DistrictFilterPrevView.as_view(), name='district_filter'),
    url(r'^target_cbo_filter/', CBOFilterView.as_view(), name='target_cbo_filter'),
    url(r'^target_userpl_filter/', CBOFilterView.as_view(), name='target_userpl_filter'),
]