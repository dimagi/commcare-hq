import itertools

from django.apps import apps
from testil import eq

from corehq.apps.dump_reload.sql.dump import _get_app_list
from corehq.apps.dump_reload.util import get_model_label

# TODO: determine which of these should not be ignored
IGNORE_MODELS = {
    "accounting.BillingAccount",
    "accounting.BillingContactInfo",
    "accounting.BillingRecord",
    "accounting.CreditAdjustment",
    "accounting.CreditLine",
    "accounting.Currency",
    "accounting.CustomerBillingRecord",
    "accounting.CustomerInvoice",
    "accounting.CustomerInvoiceCommunicationHistory",
    "accounting.DefaultProductPlan",
    "accounting.DomainUserHistory",
    "accounting.Feature",
    "accounting.FeatureRate",
    "accounting.Invoice",
    "accounting.InvoiceCommunicationHistory",
    "accounting.LineItem",
    "accounting.PaymentMethod",
    "accounting.PaymentRecord",
    "accounting.SoftwarePlan",
    "accounting.SoftwarePlanVersion",
    "accounting.SoftwareProductRate",
    "accounting.StripePaymentMethod",
    "accounting.Subscriber",
    "accounting.Subscription",
    "accounting.SubscriptionAdjustment",
    "accounting.WireBillingRecord",
    "accounting.WireInvoice",
    "accounting.WirePrepaymentBillingRecord",
    "accounting.WirePrepaymentInvoice",
    "admin.LogEntry",
    "aggregate_ucrs.AggregateTableDefinition",
    "aggregate_ucrs.PrimaryColumn",
    "aggregate_ucrs.SecondaryColumn",
    "aggregate_ucrs.SecondaryTableDefinition",
    "aggregate_ucrs.TimeAggregationDefinition",
    "analytics.PartnerAnalyticsContact",
    "analytics.PartnerAnalyticsDataPoint",
    "analytics.PartnerAnalyticsReport",
    "api.ApiUser",
    "app_manager.ExchangeApplication",
    "app_manager.ResourceOverride",
    "auditcare.AccessAudit",
    "auditcare.AuditcareMigrationMeta",
    "auditcare.HttpAccept",
    "auditcare.NavigationEventAudit",
    "auditcare.UserAgent",
    "auditcare.ViewName",
    "auth.Group",
    "auth.Permission",
    "blobs.BlobMigrationState",
    "blobs.DeletedBlobMeta",
    "case_search.IgnorePatterns",
    "contenttypes.ContentType",
    "couchforms.UnfinishedArchiveStub",
    "couchforms.UnfinishedSubmissionStub",
    "custom_data_fields.CustomDataFieldsProfile",
    "data_analytics.GIRRow",
    "data_analytics.MALTRow",
    "data_interfaces.CaseDeduplicationActionDefinition",
    "data_interfaces.CaseDuplicate",
    "dhis2.SQLDataSetMap",
    "dhis2.SQLDataValueMap",
    "django_celery_results.TaskResult",
    "django_celery_results.ChordCounter",
    "django_celery_results.GroupResult",
    "django_digest.PartialDigest",
    "django_digest.UserNonce",
    "django_prbac.Grant",
    "django_prbac.Role",
    "django_prbac.UserRole",
    "domain.AllowedUCRExpressionSettings",
    "domain.DomainAuditRecordEntry",
    "domain.ProjectLimit",
    "domain.SuperuserProjectEntryRecord",
    "domain.TransferDomainRequest",
    "dropbox.DropboxUploadHelper",
    "enterprise.EnterpriseMobileWorkerSettings",
    "enterprise.EnterprisePermissions",
    "export.DefaultExportSettings",
    "export.EmailExportWhenDoneRequest",
    "export.IncrementalExport",
    "export.IncrementalExportCheckpoint",
    "export.LedgerSectionEntry",
    "fhir.FHIRImportConfig",
    "fhir.FHIRImportResourceProperty",
    "fhir.FHIRImportResourceType",
    "fhir.ResourceTypeRelationship",
    "fixtures.UserLookupTableStatus",
    "form_processor.DeprecatedXFormAttachmentSQL",
    "hqadmin.HistoricalPillowCheckpoint",
    "hqadmin.HqDeploy",
    "hqwebapp.HQOauthApplication",
    "hqwebapp.MaintenanceAlert",
    "hqwebapp.UserAccessLog",
    "hqwebapp.UserAgent",
    "integration.DialerSettings",
    "integration.GaenOtpServerSettings",
    "integration.HmacCalloutSettings",
    "integration.SimprintsIntegration",
    "ivr.Call",
    "motech.RequestLog",
    "notifications.DismissedUINotify",
    "notifications.LastSeenNotification",
    "notifications.Notification",
    "oauth2_provider.AccessToken",
    "oauth2_provider.Application",
    "oauth2_provider.Grant",
    "oauth2_provider.IDToken",
    "oauth2_provider.RefreshToken",
    "oauth_integrations.GoogleApiToken",
    "oauth_integrations.LiveGoogleSheetRefreshStatus",
    "oauth_integrations.LiveGoogleSheetSchedule",
    "ota.DeviceLogRequest",
    "ota.MobileRecoveryMeasure",
    "ota.SerialIdBucket",
    "otp_static.StaticDevice",
    "otp_static.StaticToken",
    "otp_totp.TOTPDevice",
    "phone.SyncLogSQL",
    "pillow_retry.PillowError",
    "pillowtop.DjangoPillowCheckpoint",
    "pillowtop.KafkaCheckpoint",
    "project_limits.DynamicRateDefinition",
    "project_limits.RateLimitedTwoFactorLog",
    "registration.AsyncSignupRequest",
    "registration.RegistrationRequest",
    "registry.DataRegistry",
    "registry.RegistryAuditLog",
    "registry.RegistryGrant",
    "registry.RegistryInvitation",
    "reminders.EmailUsage",
    "reports.ReportsSidebarOrdering",
    "reports.TableauServer",
    "reports.TableauVisualization",
    "saved_reports.ScheduledReportLog",
    "saved_reports.ScheduledReportsCheckpoint",
    "scheduling.MigratedReminder",
    "scheduling.SMSCallbackContent",
    "sessions.Session",
    "sites.Site",
    "sms.DailyOutboundSMSLimitReached",
    "sms.Email",
    "sms.ExpectedCallback",
    "sms.MigrationStatus",
    "sms.MobileBackendInvitation",
    "sms.PhoneBlacklist",
    "sms.SQLLastReadMessage",
    "smsbillables.SmsBillable",
    "smsbillables.SmsGatewayFee",
    "smsbillables.SmsGatewayFeeCriteria",
    "smsbillables.SmsUsageFee",
    "smsbillables.SmsUsageFeeCriteria",
    "sso.AuthenticatedEmailDomain",
    "sso.IdentityProvider",
    "sso.SsoTestUser",
    "sso.TrustedIdentityProvider",
    "sso.UserExemptFromSingleSignOn",
    "start_enterprise.StartEnterpriseDeliveryReceipt",
    "tastypie.ApiAccess",
    "tastypie.ApiKey",
    "telerivet.IncomingRequest",
    "toggle_ui.ToggleAudit",
    "two_factor.PhoneDevice",
    "user_importer.UserUploadRecord",
    "userreports.AsyncIndicator",
    "userreports.DataSourceActionLog",
    "userreports.InvalidUCRData",
    "userreports.ReportComparisonDiff",
    "userreports.ReportComparisonException",
    "userreports.ReportComparisonTiming",
    "userreports.UCRExpression",
    "users.DeactivateMobileWorkerTrigger",
    "users.DomainRequest",
    "users.HQApiKey",
    "users.Invitation",
    "users.Permission",
    "users.UserHistory",
    "users.UserReportingMetadataStaging",
    "util.BouncedEmail",
    "util.ComplaintBounceMeta",
    "util.PermanentBounceMeta",
    "util.TransientBounceEmail",
}


def test_domain_dump_sql_models():
    dump_apps = _get_app_list(set(), set())
    covered_models = set(itertools.chain.from_iterable(dump_apps.values()))

    def _ignore_model(model):
        if not model._meta.managed:
            return True

        if get_model_label(model) in IGNORE_MODELS:
            return True

        if model._meta.proxy:
            return model._meta.concrete_model in covered_models

        # Used in Couch to SQL migration tests
        return model.__name__ == 'DummySQLModel'

    installed_models = {
        model for model in apps.get_models() if not _ignore_model(model)
    }

    uncovered_models = [
        get_model_label(model) for model in installed_models - covered_models
    ]
    assert not uncovered_models, ("Not all Django models are covered by domain dump.\n"
        + '\n'.join(sorted(uncovered_models)))
