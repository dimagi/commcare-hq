from collections import namedtuple
from uuid import uuid4

from corehq.apps.smsforms.models import XFormsSessionSynchronization, RunningSessionInfo


def test():
    phone_number_a = _clean_up_number('15555555555')
    phone_number_b = _clean_up_number('15555555554')
    session_a_1 = FakeSession(session_id=str(uuid4()), phone_number=phone_number_a, connection_id='Alpha')
    session_a_2 = FakeSession(session_id=str(uuid4()), phone_number=phone_number_a, connection_id='Beta')
    session_b_1 = FakeSession(session_id=str(uuid4()), phone_number=phone_number_b, connection_id='Kappa')

    # Nothing set yet, so it can be claimed
    assert XFormsSessionSynchronization.could_maybe_claim_phone_number_for_session_id(phone_number_a, session_a_1.session_id)
    assert XFormsSessionSynchronization.could_maybe_claim_phone_number_for_session_id(phone_number_a, session_a_2.session_id)
    # Claim succeeds
    assert XFormsSessionSynchronization.claim_phone_number_for_session(phone_number_a, session_a_1)
    # Claim for same number fails
    assert not XFormsSessionSynchronization.could_maybe_claim_phone_number_for_session_id(phone_number_a, session_a_2.session_id)
    assert not XFormsSessionSynchronization.claim_phone_number_for_session(phone_number_a, session_a_2)
    # But same session can re-claim it
    assert XFormsSessionSynchronization.claim_phone_number_for_session(phone_number_a, session_a_1)
    # And another session can claim another number
    assert XFormsSessionSynchronization.claim_phone_number_for_session(phone_number_b, session_b_1)
    # And if the first session releases the first number
    XFormsSessionSynchronization.release_phone_number_from_session(phone_number_a, session_a_1)
    # Then the contact is still set
    assert XFormsSessionSynchronization.get_running_session_info_for_phone_number(phone_number_a).contact_id == 'Alpha'
    # But the other session (that couldn't before) can claim it now
    assert XFormsSessionSynchronization.claim_phone_number_for_session(phone_number_a, session_a_2)


class FakeSession(namedtuple('FakeSession', ['session_id', 'phone_number', 'connection_id'])):
    expire_after = 60


def _clean_up_number(phone_number):
    XFormsSessionSynchronization._set_running_session_info_for_phone_number(
        phone_number, RunningSessionInfo(None, None),
        expiry=10
    )
    return phone_number
