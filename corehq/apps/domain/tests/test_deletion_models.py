import itertools

from django.apps import apps
from testil import eq

from corehq.apps.domain.deletion import DOMAIN_DELETE_OPERATIONS
from corehq.apps.dump_reload.util import get_model_label

IGNORE_APPS = {
    'aaa',
    'accounting',
    'analytics',
    'admin',
    'auditcare',
    'captcha',
    'contenttypes',
    'django_celery_results',
    'django_digest',
    'django_prbac',
    'enterprise',
    'form_processor',
    'hqadmin',
    'hqwebapp',
    'icds',
    'icds_reports',
    'notifications',
    'oauth2_provider',
    'phonelog',  # these are deleted after 60 days regardless
    'pillow_retry',
    'pillowtop',
    'project_limits',
    'saved_reports',
    'sessions',
    'sites',
    'smsbillables',
    'start_enterprise',  # TODO delete this along with SMSs
    'tastypie',
    'telerivet',
    'toggles',
    'toggle_ui',
    'sso',
}

IGNORE_MODELS = {
    'api.ApiUser',
    'app_execution.AppWorkflowConfig',
    'app_execution.AppExecutionLog',
    'app_manager.ExchangeApplication',
    'auth.Group',
    'auth.Permission',
    'blobs.BlobMeta',
    'blobs.BlobMigrationState',
    'blobs.DeletedBlobMeta',
    'cleanup.DeletedCouchDoc',
    'cleanup.DeletedSQLDoc',
    'domain.DomainAuditRecordEntry',
    'domain.SuperuserProjectEntryRecord',
    'dropbox.DropboxUploadHelper',
    'export.DefaultExportSettings',
    'experiments.ExperimentEnabler',
    'field_audit.AuditEvent',
    'fixtures.UserLookupTableStatus',
    'fixtures.LookupTableRow',          # handled by cascading delete
    'fixtures.LookupTableRowOwner',     # handled by cascading delete
    'registration.AsyncSignupRequest',
    'registration.SelfSignupWorkflow',
    'repeaters.RepeatRecord',         # handled by cascading delete
    'repeaters.RepeatRecordAttempt',  # handled by cascading delete
    'sms.MigrationStatus',
    'util.BouncedEmail',
    'util.ComplaintBounceMeta',
    'util.PermanentBounceMeta',
    'util.TransientBounceEmail',
    'users.ConnectIDUserLink',       # handled by cascading delete of django user model
    'users.ConnectIDMessagingKey',   # handled by cascading delete of user link model (from user model)
    'users.InvitationHistory',
    'users.UserHistory',
    'ota.IntegritySamplePercentage',
}


def test_deletion_sql_models():
    covered_models = set(itertools.chain.from_iterable(
        op.get_model_classes() for op in DOMAIN_DELETE_OPERATIONS
    ))

    def _ignore_model(model):
        if not model._meta.managed:
            return True

        if model._meta.app_label in IGNORE_APPS:
            return True

        if get_model_label(model) in IGNORE_MODELS:
            return True

        if model._meta.proxy:
            return model._meta.concrete_model in covered_models

        # Used in Couch to SQL migration tests
        if model.__name__ == 'DummySQLModel':
            return True

    installed_models = {
        model for model in apps.get_models() if not _ignore_model(model)
    }

    uncovered_models = installed_models - covered_models
    eq(uncovered_models, set(), "Not all Django models are covered by domain deletion.")
