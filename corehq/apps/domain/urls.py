import sys
from django.conf.urls import url
from django.contrib.auth.views import (
    password_reset, password_change, password_change_done, password_reset_done,
    password_reset_complete,
)
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils.translation import ugettext as _
from django.conf import settings
from django.views.generic import RedirectView

from corehq.apps.callcenter.views import CallCenterOwnerOptionsView
from corehq.apps.domain.forms import ConfidentialPasswordResetForm, HQSetPasswordForm
from corehq.apps.domain.views import (
    EditBasicProjectInfoView, EditPrivacySecurityView,
    DefaultProjectSettingsView, EditMyProjectSettingsView,
    ExchangeSnapshotsView, CreateNewExchangeSnapshotView,
    ManageProjectMediaView, DomainForwardingOptionsView,
    AddRepeaterView, EditInternalDomainInfoView, EditInternalCalculationsView,
    DomainSubscriptionView, SelectPlanView, ConfirmSelectedPlanView,
    SelectedEnterprisePlanView, ConfirmBillingAccountInfoView, ProBonoView,
    EditExistingBillingAccountView, DomainBillingStatementsView,
    BillingStatementPdfView,
    FeaturePreviewsView, ConfirmSubscriptionRenewalView,
    InvoiceStripePaymentView, CreditsStripePaymentView, SMSRatesView,
    AddFormRepeaterView, DomainForwardingRepeatRecords,
    FeatureFlagsView, TransferDomainView,
    ActivateTransferDomainView, DeactivateTransferDomainView,
    BulkStripePaymentView, InternalSubscriptionManagementView,
    WireInvoiceView, SubscriptionRenewalView, CreditsWireInvoiceView,
    CardsView, CardView, PasswordResetView,
    CaseSearchConfigView,
    EditOpenClinicaSettingsView,
    autocomplete_fields, test_repeater, drop_repeater, set_published_snapshot, cancel_repeat_record,
    calculated_properties, requeue_repeat_record,
    toggle_diff,
    select,
    CalendarFixtureConfigView,
    LocationFixtureConfigView,
    Dhis2ConnectionView,
)
from corehq.apps.repeaters.views import AddCaseRepeaterView, RepeatRecordView
from corehq.apps.reports.dispatcher import DomainReportDispatcher

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
        vals = {
            'current_page': {'page_name': _('Oops!')},
            'error_msg': 'There was a problem with your request',
            'error_details': sys.exc_info(),
            'show_homepage_link': 1,
        }
        return render_to_response('error.html', vals, context_instance=RequestContext(request))


# auth templates are normally in 'registration,'but that's too confusing a name, given that this app has
# both user and domain registration. Move them somewhere more descriptive.

def auth_pages_path(page):
    return {'template_name':'login_and_password/' + page}


def extend(d1, d2):
    return dict(d1.items() + d2.items())

urlpatterns =[
    url(r'^domain/select/$', select, name='domain_select'),
    url(r'^domain/autocomplete/(?P<field>[\w-]+)/$', autocomplete_fields, name='domain_autocomplete_fields'),
    url(r'^domain/transfer/(?P<guid>\w+)/activate$',
        ActivateTransferDomainView.as_view(), name='activate_transfer_domain'),
    url(r'^domain/transfer/(?P<guid>\w+)/deactivate$',
        DeactivateTransferDomainView.as_view(), name='deactivate_transfer_domain'),
] + [
    url(r'^accounts/password_change/$', password_change, auth_pages_path('password_change_form.html'), name='password_change'),
    url(r'^accounts/password_change_done/$', password_change_done,
        extend(auth_pages_path('password_change_done.html'),
               {'extra_context': {'current_page': {'page_name': _('Password Change Complete')}}}),
        name='password_change_done'),

    url(r'^accounts/password_reset_email/$', exception_safe_password_reset,
        extend(auth_pages_path('password_reset_form.html'),
               {'password_reset_form': ConfidentialPasswordResetForm,
                'from_email': settings.DEFAULT_FROM_EMAIL,
                'extra_context': {'current_page': {'page_name': _('Password Reset')}}}),
        name='password_reset_email'),
    url(r'^accounts/password_reset_email/done/$', password_reset_done,
        extend(auth_pages_path('password_reset_done.html'),
               {'extra_context': {'current_page': {'page_name': _('Reset My Password')}}}),
        name='password_reset_done'),

    url(r'^accounts/password_reset_confirm/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>.+)/$',
        PasswordResetView.as_view(),  extend(auth_pages_path('password_reset_confirm.html'),
                                                {'set_password_form': HQSetPasswordForm,
                                                'extra_context': {'current_page':
                                                    {'page_name': _('Password Reset Confirmation')}}}),
        name=PasswordResetView.urlname),
    url(r'^accounts/password_reset_confirm/done/$', password_reset_complete,
        extend(auth_pages_path('password_reset_complete.html'),
               {'extra_context': {'current_page': {'page_name': _('Password Reset Complete')}}}),
        name='password_reset_complete')
]


domain_settings = [
    url(r'^$', DefaultProjectSettingsView.as_view(), name=DefaultProjectSettingsView.urlname),
    url(r'^my_settings/$', EditMyProjectSettingsView.as_view(), name=EditMyProjectSettingsView.urlname),
    url(r'^basic/$', EditBasicProjectInfoView.as_view(), name=EditBasicProjectInfoView.urlname),
    url(r'^call_center_owner_options/', CallCenterOwnerOptionsView.as_view(),
        name=CallCenterOwnerOptionsView.url_name),
    url(r'^privacy/$', EditPrivacySecurityView.as_view(), name=EditPrivacySecurityView.urlname),
    url(r'^openclinica/$', EditOpenClinicaSettingsView.as_view(), name=EditOpenClinicaSettingsView.urlname),
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
    url(r'^subscription/credis/make_wire_payment/$', CreditsWireInvoiceView.as_view(),
        name=CreditsWireInvoiceView.urlname),
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
    url(r'^billing/make_wire_invoice/$', WireInvoiceView.as_view(),
        name=WireInvoiceView.urlname),
    url(r'^billing/cards/$', CardsView.as_view(), name=CardsView.url_name),
    url(r'^billing/cards/(?P<card_token>card_[\w]+)/$', CardView.as_view(), name=CardView.url_name),
    url(r'^subscription/$', DomainSubscriptionView.as_view(), name=DomainSubscriptionView.urlname),
    url(r'^subscription/renew/$', SubscriptionRenewalView.as_view(),
        name=SubscriptionRenewalView.urlname),
    url(r'^subscription/renew/confirm/$', ConfirmSubscriptionRenewalView.as_view(),
        name=ConfirmSubscriptionRenewalView.urlname),
    url(r'^internal_subscription_management/$', InternalSubscriptionManagementView.as_view(),
        name=InternalSubscriptionManagementView.urlname),
    url(r'^billing_information/$', EditExistingBillingAccountView.as_view(),
        name=EditExistingBillingAccountView.urlname),
    url(r'^repeat_record/', RepeatRecordView.as_view(), name=RepeatRecordView.urlname),
    url(r'^repeat_record_report/cancel/', cancel_repeat_record, name='cancel_repeat_record'),
    url(r'^repeat_record_report/requeue/', requeue_repeat_record, name='requeue_repeat_record'),
    url(r'^forwarding/$', DomainForwardingOptionsView.as_view(), name=DomainForwardingOptionsView.urlname),
    url(r'^forwarding/new/FormRepeater/$', AddFormRepeaterView.as_view(), {'repeater_type': 'FormRepeater'},
        name=AddFormRepeaterView.urlname),
    url(r'^forwarding/new/CaseRepeater/$', AddCaseRepeaterView.as_view(), {'repeater_type': 'CaseRepeater'},
        name=AddCaseRepeaterView.urlname),
    url(r'^forwarding/new/(?P<repeater_type>\w+)/$', AddRepeaterView.as_view(), name=AddRepeaterView.urlname),
    url(r'^forwarding/test/$', test_repeater, name='test_repeater'),
    url(r'^forwarding/(?P<repeater_id>[\w-]+)/stop/$', drop_repeater, name='drop_repeater'),
    url(r'^dhis2/conn/$', Dhis2ConnectionView.as_view(), name=Dhis2ConnectionView.urlname),
    url(r'^snapshots/set_published/(?P<snapshot_name>[\w-]+)/$', set_published_snapshot, name='domain_set_published'),
    url(r'^snapshots/set_published/$', set_published_snapshot, name='domain_clear_published'),
    url(r'^snapshots/$', ExchangeSnapshotsView.as_view(), name=ExchangeSnapshotsView.urlname),
    url(r'^transfer/$', TransferDomainView.as_view(), name=TransferDomainView.urlname),
    url(r'^snapshots/new/$', CreateNewExchangeSnapshotView.as_view(), name=CreateNewExchangeSnapshotView.urlname),
    url(r'^multimedia/$', ManageProjectMediaView.as_view(), name=ManageProjectMediaView.urlname),
    url(r'^case_search/$', CaseSearchConfigView.as_view(), name=CaseSearchConfigView.urlname),
    url(r'^calendar_settings/$', CalendarFixtureConfigView.as_view(), name=CalendarFixtureConfigView.urlname),
    url(r'^location_settings/$', LocationFixtureConfigView.as_view(), name=LocationFixtureConfigView.urlname),
    url(r'^commtrack/settings/$', RedirectView.as_view(url='commtrack_settings', permanent=True)),
    url(r'^internal/info/$', EditInternalDomainInfoView.as_view(), name=EditInternalDomainInfoView.urlname),
    url(r'^internal/calculations/$', EditInternalCalculationsView.as_view(), name=EditInternalCalculationsView.urlname),
    url(r'^internal/calculated_properties/$', calculated_properties, name='calculated_properties'),
    url(r'^previews/$', FeaturePreviewsView.as_view(), name=FeaturePreviewsView.urlname),
    url(r'^flags/$', FeatureFlagsView.as_view(), name=FeatureFlagsView.urlname),
    url(r'^toggle_diff/$', toggle_diff, name='toggle_diff'),
    url(r'^sms_rates/$', SMSRatesView.as_view(), name=SMSRatesView.urlname),
    DomainReportDispatcher.url_pattern()
]
