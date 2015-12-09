from corehq.apps.commtrack.tests.util import TEST_USER, TEST_DOMAIN, TEST_NUMBER, TEST_PASSWORD, TEST_BACKEND
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.interfaces.supply import SupplyInterface


def bootstrap_user(loc, username=TEST_USER, domain=TEST_DOMAIN,
                   phone_number=TEST_NUMBER, password=TEST_PASSWORD,
                   backend=TEST_BACKEND, first_name='', last_name='',
                   home_loc=None, user_data=None,
                   ):
    user_data = user_data or {}
    user = CommCareUser.create(
        domain,
        username,
        password,
        phone_numbers=[phone_number],
        user_data=user_data,
        first_name=first_name,
        last_name=last_name
    )
    if home_loc == loc.site_code:
        interface = SupplyInterface(domain)
        if not interface.get_by_location(loc):
            interface.create_from_location(domain, loc)

        user.set_location(loc)

    user.save_verified_number(domain, phone_number, verified=True, backend_id=backend)
    return CommCareUser.wrap(user.to_json())
