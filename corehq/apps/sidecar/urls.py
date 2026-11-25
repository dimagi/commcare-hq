from django.urls import path

from .views import SidecarAppView

urlpatterns = [
    path('<slug:slug>/', SidecarAppView.as_view(), name=SidecarAppView.urlname),
]
