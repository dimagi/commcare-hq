from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.domain.models import Domain

DATA_CLEANING_TEST_APP_NAME = "Plant Care (Data Cleaning Test)"


def is_real_domain(domain):
    domain_obj = Domain.get_by_name(domain)
    return domain_obj is not None


def get_domain_missing_error(domain):
    return f"Domain {domain} does not exist."


def get_fake_app(domain):
    for app in get_apps_in_domain(domain):
        if app.name == DATA_CLEANING_TEST_APP_NAME:
            return app
    return None
