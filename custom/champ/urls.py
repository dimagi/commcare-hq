from __future__ import absolute_import
from django.conf.urls import url

from custom.champ.views import PrevisionVsAchievementsView

urlpatterns = [
    url(r'^champ_pva/', PrevisionVsAchievementsView.as_view(), name='champ_pva'),
]