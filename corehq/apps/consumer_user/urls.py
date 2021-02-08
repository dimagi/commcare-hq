from django.urls import path

from .views import *


urlpatterns = [
    path('', list_view),
    path('signup/', register_view),
    path('login/', login_view, name='login'),
    path('homepage/', success_view, name='homepage'),
    path('<int:consumer_user_id>/', detail_view),
    path('<int:consumer_user_id>/delete/', delete_view),
]
