from django.urls import path

from .views import delete_view, detail_view, list_view, login_view, register_view, success_view

app_name = 'consumer_user'

urlpatterns = [
    path('', list_view),
    path('signup/<invitation>/', register_view),
    path('login/', login_view, name='patient_login'),
    path('homepage/', success_view, name='patient_homepage'),
    path('<int:consumer_user_id>/', detail_view),
    path('<int:consumer_user_id>/delete/', delete_view),
]
