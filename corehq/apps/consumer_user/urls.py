from django.conf import settings
from django.contrib.auth.views import PasswordChangeView, PasswordChangeDoneView, PasswordResetView, \
    PasswordResetDoneView, PasswordResetCompleteView
from django.urls import path, re_path, reverse_lazy
from django.utils.translation import ugettext as _

from .forms.password_reset_form import ConsumerUserSetPasswordForm, ConfidentialPasswordResetForm
from .views import login_view, register_view, success_view, logout_view, change_password_view, \
    domains_and_cases_list_view, change_contact_details_view, CustomPasswordResetView

app_name = 'consumer_user'

PASSWORD_RESET_KWARGS = {
    'template_name': 'reset_password/password_reset_form.html',
    'form_class': ConfidentialPasswordResetForm,
    'from_email': settings.DEFAULT_FROM_EMAIL,
    'success_url': reverse_lazy('consumer_user:password_reset_done'),
    'extra_context': {'current_page': {'page_name': _('Password Reset')}}
}

PASSWORD_RESET_DONE_KWARGS = {
    'template_name': 'reset_password/password_reset_done.html',
    'extra_context': {'current_page': {'page_name': _('Reset My Password')}}
}

urlpatterns = [
    path('signup/<invitation>/', register_view, name='patient_register'),
    path('login/', login_view, name='patient_login'),
    path('login/<invitation>/', login_view, name='patient_login_with_invitation'),
    path('logout/', logout_view, name='patient_logout'),
    path('homepage/', success_view, name='patient_homepage'),
    path('change-password/', change_password_view, name='change_password'),
    path('domain-case-list/', domains_and_cases_list_view, name='domain_and_cases_list'),
    path('change-contact-details/', change_contact_details_view, name='change_contact_details'),
    re_path(r'accounts/password_change/$',
            PasswordChangeView.as_view(
                template_name='reset_password/password_change_form.html'),
            name='password_change'),
    re_path(r'accounts/password_change_done/$',
            PasswordChangeDoneView.as_view(
                template_name='reset_password/password_change_done.html',
                extra_context={'current_page': {'page_name': _('Password Change Complete')}}),
            name='password_change_done'),
    re_path(r'accounts/password_reset_email/$',
            PasswordResetView.as_view(**PASSWORD_RESET_KWARGS),
            name='password_reset_email'),
    re_path(r'accounts/password_reset_email/done/$',
            PasswordResetDoneView.as_view(**PASSWORD_RESET_DONE_KWARGS),
            name='password_reset_done'),
    re_path(r'accounts/password_reset_confirm/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>.+)/$',
            CustomPasswordResetView.as_view(
                template_name='reset_password/password_reset_confirm.html',
                form_class=ConsumerUserSetPasswordForm,
                success_url=reverse_lazy('consumer_user:password_reset_complete'),
                extra_context={'current_page': {'page_name': _('Password Reset Confirmation')}},
            ),
            name=CustomPasswordResetView.urlname),
    re_path(r'accounts/password_reset_confirm/done/$', PasswordResetCompleteView.as_view(
        template_name='reset_password/password_reset_complete.html',
        extra_context={'current_page': {'page_name': _('Password Reset Complete')}}),
        name='password_reset_complete'),
]
