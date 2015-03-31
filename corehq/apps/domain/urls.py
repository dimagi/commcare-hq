import sys
from django.conf.urls import *
from django.contrib.auth.views import password_reset
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.conf import settings
from django.views.generic import RedirectView

from corehq.apps.domain.forms import ConfidentialPasswordResetForm
from corehq.apps.domain.views import (
    EditBasicProjectInfoView, EditPrivacySecurityView,
    DefaultProjectSettingsView, EditMyProjectSettingsView,
    ExchangeSnapshotsView, CreateNewExchangeSnapshotView,
    ManageProjectMediaView, DomainForwardingOptionsView,
    AddRepeaterView, EditInternalDomainInfoView, EditInternalCalculationsView,
    DomainSubscriptionView, SelectPlanView, ConfirmSelectedPlanView,
    SelectedEnterprisePlanView, ConfirmBillingAccountInfoView, ProBonoView,
    EditExistingBillingAccountView, DomainBillingStatementsView,
    BillingStatementPdfView, OrgSettingsView,
    FeaturePreviewsView, ConfirmSubscriptionRenewalView,
    InvoiceStripePaymentView, CreditsStripePaymentView, SMSRatesView,
    AddFormRepeaterView, AddOpsUserAsDomainAdminView,
    FeatureFlagsView, EditDhis2SettingsView, TransferDomainView,
    ActivateTransferDomainView, DeactivateTransferDomainView,
    BulkStripePaymentView)

#
# After much reading, I discovered that Django matches URLs derived from the environment
# variable PATH_INFO. This is set by your webserver, so any misconfiguration there will
# mess this up. In Apache, the WSGIScriptAliasMatch pulls off the mount point directory,
# and puts everything that follows it into PATH_INFO. Those (mount-point-less) paths are
# what is matched in urlpatterns.
#

# All of these auth functions have custom templates in registration/, with the default names they expect.
#
# Django docs on password reset are weak. See these links instead:
#
# http://streamhacker.com/2009/09/19/django-ia-auth-password-reset/
# http://www.rkblog.rk.edu.pl/w/p/password-reset-django-10/
# http://blog.montylounge.com/2009/jul/12/django-forgot-password/
#
# Note that the provided password reset function raises SMTP errors if there's any
# problem with the mailserver. Catch that more elegantly with a simple wrapper.


def exception_safe_password_reset(request, *args, **kwargs):
    try:
        return password_reset(request, *args, **kwargs)
    except None: 
        vals = {'error_msg':'There was a problem with your request',
                'error_details':sys.exc_info(),
                'show_homepage_link': 1 }
        return render_to_response('error.html', vals, context_instance=RequestContext(request))


# auth templates are normally in 'registration,'but that's too confusing a name, given that this app has
# both user and domain registration. Move them somewhere more descriptive.

def auth_pages_path(page):
    return {'template_name':'login_and_password/' + page}

def extend(d1, d2):
    return dict(d1.items() + d2.items())

urlpatterns =\
    patterns('corehq.apps.domain.views',
        url(r'^domain/select/$', 'select', name='domain_select'),
        url(r'^domain/autocomplete/(?P<field>\w+)/$', 'autocomplete_fields', name='domain_autocomplete_fields'),
        url(r'^domain/incomplete_email/$', 'incomplete_email'),
        url(r'^domain/transfer/(?P<guid>\w+)/activate$',
            ActivateTransferDomainView.as_view(), name='activate_transfer_domain'),
        url(r'^domain/transfer/(?P<guid>\w+)/deactivate$',
            DeactivateTransferDomainView.as_view(), name='deactivate_transfer_domain'),
    ) +\
    patterns('django.contrib.auth.views',
        url(r'^accounts/password_change/$', 'password_change', auth_pages_path('password_change_form.html'), name='password_change'),
        url(r'^accounts/password_change_done/$', 'password_change_done', auth_pages_path('password_change_done.html'),
            name='password_change_done'),

        url(r'^accounts/password_reset_email/$', exception_safe_password_reset, extend(auth_pages_path('password_reset_form.html'),
                                                                                       { 'password_reset_form': ConfidentialPasswordResetForm,
                                                                                         'from_email':settings.DEFAULT_FROM_EMAIL}),
            name='password_reset_email'),
        url(r'^accounts/password_reset_email/done/$', 'password_reset_done', auth_pages_path('password_reset_done.html'),
            name='password_reset_done'),

        url(r'^accounts/password_reset_confirm/(?P<uidb36>[0-9A-Za-z]+)-(?P<token>.+)/$', 'password_reset_confirm',
            auth_pages_path('password_reset_confirm.html'), name="confirm_password_reset" ),
        url(r'^accounts/password_reset_confirm/done/$', 'password_reset_complete', auth_pages_path('password_reset_complete.html'),
            name='password_reset_complete')
    )


domain_settings = patterns(
    'corehq.apps.domain.views',
    url(r'^$', DefaultProjectSettingsView.as_view(), name=DefaultProjectSettingsView.urlname),
    url(r'^my_settings/$', EditMyProjectSettingsView.as_view(), name=EditMyProjectSettingsView.urlname),
    url(r'^basic/$', EditBasicProjectInfoView.as_view(), name=EditBasicProjectInfoView.urlname),
    url(r'^privacy/$', EditPrivacySecurityView.as_view(), name=EditPrivacySecurityView.urlname),
    url(r'^dhis2/$', EditDhis2SettingsView.as_view(), name=EditDhis2SettingsView.urlname),
    url(r'^subscription/change/$', SelectPlanView.as_view(), name=SelectPlanView.urlname),
    url(r'^subscription/change/confirm/$', ConfirmSelectedPlanView.as_view(),
        name=ConfirmSelectedPlanView.urlname),
    url(r'^subscription/change/request/$', SelectedEnterprisePlanView.as_view(),
        name=SelectedEnterprisePlanView.urlname),
    url(r'^subscription/change/account/$', ConfirmBillingAccountInfoView.as_view(),
        name=ConfirmBillingAccountInfoView.urlname),
    url(r'^subscription/pro_bono/$', ProBonoView.as_view(), name=ProBonoView.urlname),
    url(r'^subscription/credits/make_payment/$', CreditsStripePaymentView.as_view(),
        name=CreditsStripePaymentView.urlname),
    url(r'^billing/statements/download/(?P<statement_id>[\w-]+).pdf$',
        BillingStatementPdfView.as_view(),
        name=BillingStatementPdfView.urlname
    ),
    url(r'^billing/statements/$', DomainBillingStatementsView.as_view(),
        name=DomainBillingStatementsView.urlname),
    url(r'^billing/make_payment/$', InvoiceStripePaymentView.as_view(),
        name=InvoiceStripePaymentView.urlname),
    url(r'^billing/make_bulk_payment/$', BulkStripePaymentView.as_view(),
        name=BulkStripePaymentView.urlname),
    url(r'^billing/join_billing_admins/$', AddOpsUserAsDomainAdminView.as_view(),
        name=AddOpsUserAsDomainAdminView.urlname),
    url(r'^subscription/$', DomainSubscriptionView.as_view(), name=DomainSubscriptionView.urlname),
    url(r'^subscription/renew/$', ConfirmSubscriptionRenewalView.as_view(),
        name=ConfirmSubscriptionRenewalView.urlname),
    url(r'^billing_information/$', EditExistingBillingAccountView.as_view(),
        name=EditExistingBillingAccountView.urlname),
    url(r'^forwarding/$', DomainForwardingOptionsView.as_view(), name=DomainForwardingOptionsView.urlname),
    url(r'^forwarding/new/FormRepeater/$', AddFormRepeaterView.as_view(), {'repeater_type': 'FormRepeater'},
        name=AddFormRepeaterView.urlname),
    url(r'^forwarding/new/(?P<repeater_type>\w+)/$', AddRepeaterView.as_view(), name=AddRepeaterView.urlname),
    url(r'^forwarding/test/$', 'test_repeater', name='test_repeater'),
    url(r'^forwarding/(?P<repeater_id>[\w-]+)/stop/$', 'drop_repeater', name='drop_repeater'),
    url(r'^snapshots/set_published/(?P<snapshot_name>[\w-]+)/$', 'set_published_snapshot', name='domain_set_published'),
    url(r'^snapshots/set_published/$', 'set_published_snapshot', name='domain_clear_published'),
    url(r'^snapshots/$', ExchangeSnapshotsView.as_view(), name=ExchangeSnapshotsView.urlname),
    url(r'^transfer/$', TransferDomainView.as_view(), name=TransferDomainView.urlname),
    url(r'^snapshots/new/$', CreateNewExchangeSnapshotView.as_view(), name=CreateNewExchangeSnapshotView.urlname),
    url(r'^multimedia/$', ManageProjectMediaView.as_view(), name=ManageProjectMediaView.urlname),
    url(r'^commtrack/settings/$', RedirectView.as_view(url='commtrack_settings')),
    url(r'^organization/$', OrgSettingsView.as_view(), name=OrgSettingsView.urlname),
    url(r'^organization/request/$', 'org_request', name='domain_org_request'),
    url(r'^internal/info/$', EditInternalDomainInfoView.as_view(), name=EditInternalDomainInfoView.urlname),
    url(r'^internal/calculations/$', EditInternalCalculationsView.as_view(), name=EditInternalCalculationsView.urlname),
    url(r'^internal/calculated_properties/$', 'calculated_properties', name='calculated_properties'),
    url(r'^previews/$', FeaturePreviewsView.as_view(), name=FeaturePreviewsView.urlname),
    url(r'^flags/$', FeatureFlagsView.as_view(), name=FeatureFlagsView.urlname),
    url(r'^sms_rates/$', SMSRatesView.as_view(), name=SMSRatesView.urlname),
)
