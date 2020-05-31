from collections import namedtuple
from uuid import uuid4

from corehq.apps.smsforms.models import XFormsSessionSynchronization, RunningSessionInfo, Channel


def test():
    phone_number_a = _clean_up_number('15555555555')
    phone_number_b = _clean_up_number('15555555554')
    session_a_1 = FakeSession(session_id=str(uuid4()), phone_number=phone_number_a, connection_id='Alpha')
    session_a_2 = FakeSession(session_id=str(uuid4()), phone_number=phone_number_a, connection_id='Beta')
    session_b_1 = FakeSession(session_id=str(uuid4()), phone_number=phone_number_b, connection_id='Kappa')

    # Nothing set yet, so it can be claimed
    assert XFormsSessionSynchronization.could_maybe_claim_channel_for_session(session_a_1)
    # And so can the other one
    assert XFormsSessionSynchronization.could_maybe_claim_channel_for_session(session_a_2)
    # Claim succeeds
    assert XFormsSessionSynchronization.claim_channel_for_session(session_a_1)
    # Claim for same channel fails
    assert not XFormsSessionSynchronization.could_maybe_claim_channel_for_session(session_a_2)
    assert not XFormsSessionSynchronization.claim_channel_for_session(session_a_2)
    # But same session can re-claim it
    assert XFormsSessionSynchronization.claim_channel_for_session(session_a_1)
    # And another session can claim another channel
    assert XFormsSessionSynchronization.claim_channel_for_session(session_b_1)
    # And if the first session releases the channel
    XFormsSessionSynchronization.release_channel_for_session(session_a_1)
    # Then the contact is still set
    assert XFormsSessionSynchronization.get_running_session_info_for_channel(
        Channel(BACKEND_ID, phone_number_a)
    ).contact_id == 'Alpha'
    # But the other session (that couldn't before) can claim it now
    assert XFormsSessionSynchronization.claim_channel_for_session(session_a_2)


class FakeSession(namedtuple('FakeSession', ['session_id', 'phone_number', 'connection_id'])):
    expire_after = 60

    def get_channel(self):
        return Channel(BACKEND_ID, self.phone_number)


def _clean_up_number(phone_number):
    XFormsSessionSynchronization._set_running_session_info_for_channel(
        Channel(BACKEND_ID, phone_number), RunningSessionInfo(None, None),
        expiry=10
    )
    return phone_number


BACKEND_ID = '2b00042f7481c7b056c4b410d28f33cf'
