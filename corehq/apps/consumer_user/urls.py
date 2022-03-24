from django.urls import path

from .views import (
    ConsumerUserLoginView,
    change_contact_details_view,
    change_password_view,
    homepage_view,
    logout_view,
    register_view,
)

app_name = 'consumer_user'

urlpatterns = [
    path('signup/<signed_invitation_id>/', register_view, name='register'),
    path('login/', ConsumerUserLoginView.as_view(), name='login'),
    path(
        'login/<signed_invitation_id>/',
        ConsumerUserLoginView.as_view(),
        name='login_with_invitation',
    ),
    path('logout/', logout_view, name='logout'),
    path('homepage/', homepage_view, name='homepage'),
    path('change_password/', change_password_view, name='change_password'),
    path('change_contact_details/', change_contact_details_view, name='change_contact_details'),
]
