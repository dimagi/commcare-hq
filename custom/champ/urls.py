from django.urls import re_path as url

from custom.champ.views import PrevisionVsAchievementsView, DistrictFilterPrevView, \
    CBOFilterView, PrevisionVsAchievementsTableView, ServiceUptakeView, UserGroupsFilter, OrganizationsFilter, \
    UserPLFilterView, HierarchyFilter

urlpatterns = [
    url(r'^champ_pva/', PrevisionVsAchievementsView.as_view(), name='champ_pva'),
    url(r'^champ_pva_table/', PrevisionVsAchievementsTableView.as_view(), name='champ_pva_table'),
    url(r'^service_uptake/', ServiceUptakeView.as_view(), name='service_uptake'),
    url(r'^district_filter/', DistrictFilterPrevView.as_view(), name='district_filter'),
    url(r'^target_cbo_filter/', CBOFilterView.as_view(), name='target_cbo_filter'),
    url(r'^target_userpl_filter/', UserPLFilterView.as_view(), name='target_userpl_filter'),
    url(r'^group_filter/', UserGroupsFilter.as_view(), name='group_filter'),
    url(r'^organization_filter/', OrganizationsFilter.as_view(), name='organization_filter'),
    url(r'^hierarchy/', HierarchyFilter.as_view(), name='hierarchy'),
]
