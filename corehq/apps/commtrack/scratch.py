
from corehq.apps.users.models import CommCareUser
from corehq.apps.sms import test_backend

def make_verified_contact(username, backend=test_backend.API_ID):
    """utility function to register 'verified' phone numbers for a commcare user"""
    u = CommCareUser.get_by_username(username)
    for phone in u.phone_numbers:
        u.save_verified_number(u.domain, phone, True, backend)
