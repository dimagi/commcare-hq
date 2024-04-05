from django.conf import settings

urlpatterns = []
if hasattr(settings, 'ABDM_INTEGRATOR'):
    from abdm_integrator.urls import urlpatterns as abdm_urls
    urlpatterns += abdm_urls
