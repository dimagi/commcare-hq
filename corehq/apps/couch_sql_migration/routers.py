

class DomainMigrationsRouter(object):
    """
    All models in the couch_sql_migration app (i.e. models.Undo) must
    use the "domain_migrations" database.
    """

    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'couch_sql_migration':
            return 'domain_migrations'

    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'couch_sql_migration':
            return 'domain_migrations'

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == 'couch_sql_migration':
            return db == 'domain_migrations'
