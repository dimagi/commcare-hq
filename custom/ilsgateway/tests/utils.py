from corehq.apps.commtrack.tests.util import TEST_USER, TEST_DOMAIN, TEST_NUMBER, TEST_PASSWORD, TEST_BACKEND
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.interfaces.supply import SupplyInterface


def bootstrap_user(loc, username=TEST_USER, domain=TEST_DOMAIN,
                   phone_number=TEST_NUMBER, password=TEST_PASSWORD,
                   backend=TEST_BACKEND, first_name='', last_name='',
                   home_loc=None, user_data=None, language=None
                   ):
    user_data = user_data or {}
    user = CommCareUser.create(
        domain,
        username,
        password,
        user_data=user_data,
        first_name=first_name,
        last_name=last_name
    )
    if language:
        user.language = language
    if home_loc == loc.site_code:
        interface = SupplyInterface(domain)
        if not interface.get_by_location(loc):
            interface.create_from_location(domain, loc)

        user.set_location(loc)

    user.phone_numbers = [phone_number]
    user.save()

    entry = user.get_or_create_phone_entry(phone_number)
    entry.set_two_way()
    entry.set_verified()
    entry.backend_id = backend
    entry.save()
    return CommCareUser.wrap(user.to_json())
