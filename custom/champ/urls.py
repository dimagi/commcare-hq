from __future__ import absolute_import
from django.conf.urls import url

from custom.champ.views import PrevisionVsAchievementsView, DistrictFilterPrevView, \
    CBOFilterView, PrevisionVsAchievementsTableView

urlpatterns = [
    url(r'^champ_pva/', PrevisionVsAchievementsView.as_view(), name='champ_pva'),
    url(r'^champ_pva_table/', PrevisionVsAchievementsTableView.as_view(), name='champ_pva_table'),
    url(r'^district_filter/', DistrictFilterPrevView.as_view(), name='district_filter'),
    url(r'^target_cbo_filter/', CBOFilterView.as_view(), name='target_cbo_filter'),
    url(r'^target_userpl_filter/', CBOFilterView.as_view(), name='target_userpl_filter'),
]