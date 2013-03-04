from corehq.apps.locations.models import Location
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.commtrack.util import bootstrap_default
from corehq.apps.users.models import CommCareUser

TEST_DOMAIN = 'commtrack-test'
TEST_LOCATION_TYPE = 'location'
TEST_USER = 'commtrack-user'
TEST_NUMBER = '5551234'
TEST_PASSWORD = 'secret'
TEST_BACKEND = 'test-backend'

def bootstrap_domain(domain_name=TEST_DOMAIN, requisitions_enabled=False):
    # little test utility that makes a commtrack-enabled domain with
    # a default config and a location
    domain_obj = create_domain(domain_name)
    domain_obj.commtrack_enabled = True
    domain_obj.save()
    config = bootstrap_default(domain_name)
    if requisitions_enabled:
        config.requisition_config.enabled = True
        config.save()
    return domain_obj


def bootstrap_user(username=TEST_USER, domain=TEST_DOMAIN,
                   phone_number=TEST_NUMBER, password=TEST_PASSWORD,
                   backend=TEST_BACKEND):
    user = CommCareUser.create(domain, username, password, phone_numbers=[TEST_NUMBER])
    user.save_verified_number(domain, phone_number, verified=True, backend_id=TEST_BACKEND)
    return user

def make_loc(code, name=None, domain=TEST_DOMAIN, type=TEST_LOCATION_TYPE):
    name = name or code
    loc = Location(site_code=code, name=name, domain=domain, type=type)
    loc.save()
    return loc
