from django.conf import settings
from django.urls import include, re_path as url
from django.contrib.auth.views import (
    PasswordChangeDoneView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.utils.translation import gettext as _
from django.views.generic import RedirectView

from corehq.apps.callcenter.views import CallCenterOwnerOptionsView
from corehq.apps.domain.forms import (
    ConfidentialPasswordResetForm,
    HQSetPasswordForm,
)
from corehq.apps.domain.views.accounting import (
    BillingStatementPdfView,
    BulkStripePaymentView,
    CardsView,
    CardView,
    ConfirmBillingAccountInfoView,
    ConfirmSelectedPlanView,
    ConfirmSubscriptionRenewalView,
    CreditsStripePaymentView,
    CreditsWireInvoiceView,
    DomainBillingStatementsView,
    DomainSubscriptionView,
    EditExistingBillingAccountView,
    EmailOnDowngradeView,
    InternalSubscriptionManagementView,
    InvoiceStripePaymentView,
    SelectedAnnualPlanView,
    SelectedEnterprisePlanView,
    SelectPlanView,
    SubscriptionRenewalView,
    WireInvoiceView,
    pause_subscription,
)
from corehq.apps.domain.views.base import select, accept_all_invitations
from corehq.apps.domain.views.fixtures import LocationFixtureConfigView
from corehq.apps.domain.views.internal import (
    ActivateTransferDomainView,
    DeactivateTransferDomainView,
    EditInternalCalculationsView,
    EditInternalDomainInfoView,
    FlagsAndPrivilegesView,
    ProjectLimitsView,
    TransferDomainView,
    TestBootstrap5DomainView,
    calculated_properties,
    toggle_diff,
)
from corehq.apps.domain.views.pro_bono import ProBonoView
from corehq.apps.domain.views.releases import (
    ManageReleasesByAppProfile,
    ManageReleasesByLocation,
    activate_release_restriction,
    deactivate_release_restriction,
    toggle_release_restriction_by_app_profile,
)
from corehq.apps.domain.views.settings import (
    delete_domain_alert,
    update_domain_alert_status,
    CaseSearchConfigView,
    DefaultProjectSettingsView,
    EditBasicProjectInfoView,
    EditDomainAlertView,
    EditMyProjectSettingsView,
    EditPrivacySecurityView,
    FeaturePreviewsView,
    ManageDomainAlertsView,
    ManageDomainMobileWorkersView,
    CustomPasswordResetView,
    RecoveryMeasuresHistory,
)
from corehq.apps.domain.views.sms import SMSRatesView
from corehq.apps.hqwebapp.decorators import waf_allow
from corehq.apps.integration.urls import settings_patterns as integration_settings
from corehq.apps.linked_domain.views import DomainLinkView
from corehq.apps.reports.dispatcher import DomainReportDispatcher
from corehq.motech.repeaters.views import (
    RepeatRecordView,
    cancel_repeat_record,
    requeue_repeat_record,
)

PASSWORD_RESET_KWARGS = {
    'template_name': 'login_and_password/password_reset_form.html',
    'form_class': ConfidentialPasswordResetForm,
    'from_email': settings.DEFAULT_FROM_EMAIL,
    'extra_context': {'current_page': {'page_name': _('Password Reset')}}
}

PASSWORD_RESET_DONE_KWARGS = {
    'template_name': 'login_and_password/password_reset_done.html',
    'extra_context': {'current_page': {'page_name': _('Reset My Password')}}
}


urlpatterns = [
    url(r'^domain/select/$', select, name='domain_select'),
    url(r'^domain/select_redirect/$', select, {'do_not_redirect': True}, name='domain_select_redirect'),
    url('^accept_all_invitations/$', accept_all_invitations, name='accept_all_invitations'),
    url(r'^domain/transfer/(?P<guid>\w+)/activate$',
        ActivateTransferDomainView.as_view(), name='activate_transfer_domain'),
    url(r'^domain/transfer/(?P<guid>\w+)/deactivate$',
        DeactivateTransferDomainView.as_view(), name='deactivate_transfer_domain'),
    url(r'^accounts/password_change/$',
        PasswordChangeView.as_view(
            template_name='login_and_password/password_change_form.html'),
        name='password_change'),
    url(r'^accounts/password_change_done/$',
        PasswordChangeDoneView.as_view(
            template_name='login_and_password/password_change_done.html',
            extra_context={'current_page': {'page_name': _('Password Change Complete')}}),
        name='password_change_done'),
    url(r'^accounts/password_reset_email/$',
        PasswordResetView.as_view(**PASSWORD_RESET_KWARGS), name='password_reset_email'),
    url(r'^accounts/password_reset_email/done/$',
        PasswordResetDoneView.as_view(**PASSWORD_RESET_DONE_KWARGS),
        name='password_reset_done'),
    url(r'^accounts/password_reset_confirm/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>.+)/$',
        CustomPasswordResetView.as_view(
            template_name='login_and_password/password_reset_confirm.html',
            form_class=HQSetPasswordForm,
            extra_context={'current_page': {'page_name': _('Password Reset Confirmation')}},
        ),
        name=CustomPasswordResetView.urlname),
    url(r'^accounts/password_reset_confirm/done/$', PasswordResetCompleteView.as_view(
        template_name='login_and_password/password_reset_complete.html',
        extra_context={'current_page': {'page_name': _('Password Reset Complete')}}),
        name='password_reset_complete'),
]

domain_settings = [
    url(r'^$', DefaultProjectSettingsView.as_view(), name=DefaultProjectSettingsView.urlname),
    url(r'^my_settings/$', EditMyProjectSettingsView.as_view(), name=EditMyProjectSettingsView.urlname),
    url(r'^basic/$',
        waf_allow('XSS_BODY')(EditBasicProjectInfoView.as_view()), name=EditBasicProjectInfoView.urlname),
    url(r'^call_center_owner_options/', CallCenterOwnerOptionsView.as_view(),
        name=CallCenterOwnerOptionsView.url_name),
    url(r'^privacy/$', EditPrivacySecurityView.as_view(), name=EditPrivacySecurityView.urlname),
    url(r'^subscription/change/$', SelectPlanView.as_view(), name=SelectPlanView.urlname),
    url(r'^subscription/change/confirm/$', ConfirmSelectedPlanView.as_view(),
        name=ConfirmSelectedPlanView.urlname),
    url(r'^subscription/change/request/$', SelectedEnterprisePlanView.as_view(),
        name=SelectedEnterprisePlanView.urlname),
    url(r'^subscription/change/request_annual/$', SelectedAnnualPlanView.as_view(),
        name=SelectedAnnualPlanView.urlname),
    url(r'^subscription/change/account/$', ConfirmBillingAccountInfoView.as_view(),
        name=ConfirmBillingAccountInfoView.urlname),
    url(r'^subscription/change/pause/$', pause_subscription, name='pause_subscription'),
    url(r'^subscription/change/email/$', EmailOnDowngradeView.as_view(), name=EmailOnDowngradeView.urlname),
    url(r'^subscription/pro_bono/$', ProBonoView.as_view(), name=ProBonoView.urlname),
    url(r'^subscription/credits/make_payment/$', CreditsStripePaymentView.as_view(),
        name=CreditsStripePaymentView.urlname),
    url(r'^subscription/credits/make_wire_payment/$', CreditsWireInvoiceView.as_view(),
        name=CreditsWireInvoiceView.urlname),
    url(r'^billing/statements/download/(?P<statement_id>[\w-]+).pdf$',
        BillingStatementPdfView.as_view(),
        name=BillingStatementPdfView.urlname),
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
    url(r'^integration/', include(integration_settings)),
    url(r'^transfer/$', TransferDomainView.as_view(), name=TransferDomainView.urlname),
    url(r'^case_search/$', CaseSearchConfigView.as_view(), name=CaseSearchConfigView.urlname),
    url(r'^domain_links/$', DomainLinkView.as_view(), name=DomainLinkView.urlname),
    url(r'^location_settings/$', LocationFixtureConfigView.as_view(), name=LocationFixtureConfigView.urlname),
    url(r'^commtrack/settings/$', RedirectView.as_view(url='commtrack_settings', permanent=True)),
    url(r'^internal/info/$', EditInternalDomainInfoView.as_view(), name=EditInternalDomainInfoView.urlname),
    url(r'^internal/bootstrap5/$', TestBootstrap5DomainView.as_view(), name=TestBootstrap5DomainView.urlname),
    url(r'^internal/calculations/$', EditInternalCalculationsView.as_view(),
        name=EditInternalCalculationsView.urlname),
    url(r'^internal/calculated_properties/$', calculated_properties, name='calculated_properties'),
    url(r'^previews/$', FeaturePreviewsView.as_view(), name=FeaturePreviewsView.urlname),
    url(r'^alerts/edit/(?P<alert_id>[\w\-]+)/$', EditDomainAlertView.as_view(), name=EditDomainAlertView.urlname),
    url(r'^alerts/$', ManageDomainAlertsView.as_view(), name=ManageDomainAlertsView.urlname),
    url(r'^alerts/delete/$', delete_domain_alert, name='delete_domain_alert'),
    url(r'^alerts/update_status/$', update_domain_alert_status, name='update_domain_alert_status'),
    url(r'^manage_mobile_workers/$', ManageDomainMobileWorkersView.as_view(),
        name=ManageDomainMobileWorkersView.urlname),
    url(r'^flags/$', FlagsAndPrivilegesView.as_view(), name=FlagsAndPrivilegesView.urlname),
    url(r'^project_limits/$', ProjectLimitsView.as_view(), name=ProjectLimitsView.urlname),
    url(r'^toggle_diff/$', toggle_diff, name='toggle_diff'),
    url(r'^sms_rates/$', SMSRatesView.as_view(), name=SMSRatesView.urlname),
    url(r'^recovery_measures_history/$',
        RecoveryMeasuresHistory.as_view(),
        name=RecoveryMeasuresHistory.urlname),
    url(r'^manage_releases_by_location/$', ManageReleasesByLocation.as_view(),
        name=ManageReleasesByLocation.urlname),
    url(r'^manage_releases_by_app_profile/$', ManageReleasesByAppProfile.as_view(),
        name=ManageReleasesByAppProfile.urlname),
    url(r'^deactivate_release_restriction/(?P<restriction_id>[\w-]+)/$', deactivate_release_restriction,
        name='deactivate_release_restriction'),
    url(r'^activate_release_restriction/(?P<restriction_id>[\w-]+)/$', activate_release_restriction,
        name='activate_release_restriction'),
    url(r'^toggle_release_restriction_by_app_profile/(?P<restriction_id>[\w-]+)/$',
        toggle_release_restriction_by_app_profile, name='toggle_release_restriction_by_app_profile'),
    DomainReportDispatcher.url_pattern()
]
