import itertools

from django.apps import apps
from django.db.models.fields.related import ForeignKey

from corehq.apps.dump_reload.sql.dump import _get_app_list
from corehq.apps.dump_reload.util import get_model_label

IGNORE_MODELS = {
    "accounting.BillingAccount",
    "accounting.BillingAccountWebUserHistory",
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
    "accounting.WireInvoice",   # this has a domain, but nothing else in accounting does
    "accounting.WirePrepaymentBillingRecord",
    "accounting.WirePrepaymentInvoice",
    "admin.LogEntry",
    "analytics.PartnerAnalyticsContact",
    "analytics.PartnerAnalyticsDataPoint",
    "analytics.PartnerAnalyticsReport",
    "api.ApiUser",
    "app_manager.ExchangeApplication",
    "auth.Group",
    "auth.Permission",
    "blobs.BlobMigrationState",
    "cleanup.DeletedCouchDoc",
    "cleanup.DeletedSQLDoc",
    "contenttypes.ContentType",
    "data_analytics.GIRRow",
    "data_analytics.MALTRow",
    "django_celery_results.ChordCounter",
    "django_celery_results.GroupResult",
    "django_celery_results.TaskResult",
    "django_digest.PartialDigest",
    "django_digest.UserNonce",
    "django_prbac.Grant",
    "django_prbac.Role",
    "django_prbac.UserRole",
    "dropbox.DropboxUploadHelper",
    "enterprise.EnterpriseMobileWorkerSettings",    # tied to an account, not a domain
    "enterprise.EnterprisePermissions",
    "export.DefaultExportSettings",     # tied to an account, not a domain
    "export.EmailExportWhenDoneRequest",  # transient model tied to an export task
    "form_processor.DeprecatedXFormAttachmentSQL",
    "hqadmin.HistoricalPillowCheckpoint",
    "hqadmin.HqDeploy",
    "hqwebapp.HQOauthApplication",
    "hqwebapp.UserAccessLog",
    "hqwebapp.UserAgent",
    "notifications.DismissedUINotify",
    "notifications.LastSeenNotification",
    "notifications.Notification",
    "otp_static.StaticDevice",
    "otp_static.StaticToken",
    "otp_totp.TOTPDevice",
    "phone.SyncLogSQL",  # not required and can be a lot of data
    "pillow_retry.PillowError",
    "pillowtop.DjangoPillowCheckpoint",
    "pillowtop.KafkaCheckpoint",
    "project_limits.DynamicRateDefinition",
    "project_limits.RateLimitedTwoFactorLog",

    # 'registry' models only make sense across multiple domains
    "registry.DataRegistry",
    "registry.RegistryAuditLog",
    "registry.RegistryGrant",
    "registry.RegistryInvitation",

    "sessions.Session",
    "sites.Site",
    "tastypie.ApiAccess",  # not tagged by domain
    "tastypie.ApiKey",  # not domain-specific
    "toggle_ui.ToggleAudit",
    "two_factor.PhoneDevice",
    "users.Permission",
    "util.BouncedEmail",
    "util.ComplaintBounceMeta",
    "util.PermanentBounceMeta",
    "util.TransientBounceEmail",
}

# TODO: determine which of these should not be ignored
UNKNOWN_MODELS = {
    "aggregate_ucrs.AggregateTableDefinition",
    "aggregate_ucrs.PrimaryColumn",
    "aggregate_ucrs.SecondaryColumn",
    "aggregate_ucrs.SecondaryTableDefinition",
    "aggregate_ucrs.TimeAggregationDefinition",
    "auditcare.AccessAudit",
    "auditcare.AuditcareMigrationMeta",
    "auditcare.HttpAccept",
    "auditcare.NavigationEventAudit",
    "auditcare.UserAgent",
    "auditcare.ViewName",
    "blobs.DeletedBlobMeta",
    "couchforms.UnfinishedArchiveStub",
    "couchforms.UnfinishedSubmissionStub",
    "data_interfaces.CaseDuplicate",
    "data_interfaces.CaseDuplicateNew",
    "dhis2.SQLDataSetMap",
    "dhis2.SQLDataValueMap",
    "fhir.FHIRImportConfig",
    "fhir.FHIRImportResourceProperty",
    "fhir.FHIRImportResourceType",
    "fhir.ResourceTypeRelationship",
    "field_audit.AuditEvent",
    "fixtures.UserLookupTableStatus",
    "ivr.Call",
    "oauth2_provider.AccessToken",
    "oauth2_provider.Application",
    "oauth2_provider.Grant",
    "oauth2_provider.IDToken",
    "oauth2_provider.RefreshToken",
    "oauth_integrations.GoogleApiToken",
    "oauth_integrations.LiveGoogleSheetRefreshStatus",
    "oauth_integrations.LiveGoogleSheetSchedule",
    "registration.AsyncSignupRequest",
    "registration.RegistrationRequest",
    "reminders.EmailUsage",
    "scheduling.MigratedReminder",
    "scheduling.SMSCallbackContent",
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
    "telerivet.IncomingRequest",
    "userreports.AsyncIndicator",
    "userreports.DataSourceActionLog",
    "userreports.InvalidUCRData",
    "users.HQApiKey",
    "users.UserHistory",
    "users.UserReportingMetadataStaging",
}


def test_domain_dump_sql_models():
    dump_apps = _get_app_list(set(), set())
    covered_models = set(itertools.chain.from_iterable(dump_apps.values()))

    def _ignore_model(model):
        if not model._meta.managed:
            return True

        if get_model_label(model) in IGNORE_MODELS | UNKNOWN_MODELS:
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


def test_foreign_keys_for_dumped_sql_models_are_also_included():
    IGNORE_FK_MODELS = [
        "scheduling.SMSCallbackContent",  # Model is no longer supported, so this would only impact old domains
        "users.Permission",  # Permissions are created on fresh install
        # -- If you add a model here, be sure to provide justification why it is safe to ignore --
    ]
    dump_apps = _get_app_list(set(), set())
    covered_models = set(itertools.chain.from_iterable(dump_apps.values()))

    uncovered_fks_by_model = {}
    for model in covered_models:
        foreign_keys = {field.remote_field.model for field in model._meta.fields if isinstance(field, ForeignKey)}
        uncovered_fk_models = foreign_keys - covered_models
        uncovered_foreign_keys = [
            label
            for label in [get_model_label(model) for model in uncovered_fk_models]
            if label not in IGNORE_FK_MODELS
        ]
        if uncovered_foreign_keys:
            uncovered_fks_by_model[get_model_label(model)] = uncovered_foreign_keys

    assert (
        not uncovered_fks_by_model
    ), "Not all foreign key relationships will be included in the domain dump.\n\n" + "\n\n".join(
        [
            f"{model} foreign keys to these uncovered models:\n\t" + "\n\t".join(fks)
            for model, fks in sorted(uncovered_fks_by_model.items())
        ]
    )
