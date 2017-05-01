from django.conf.urls import url
from .views import update_voucher, update_incentive


urlpatterns = [
    url(r'^update_voucher$', update_voucher, name='update_voucher'),
    url(r'^update_incentive$', update_incentive, name='update_incentive'),
]
