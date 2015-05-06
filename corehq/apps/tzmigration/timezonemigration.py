from corehq.apps.tzmigration import set_migration_started, \
    set_migration_complete


def run_timezone_migration_for_domain(domain):
    set_migration_started(domain)
    _run_timezone_migration_for_domain(domain)
    set_migration_complete(domain)


def _run_timezone_migration_for_domain(domain):
    pass
