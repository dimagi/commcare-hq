import pickle
from uuid import uuid4

import mock

from corehq.apps.smsforms.models import XFormsSessionSynchronization, RunningSessionInfo, SMSChannel, \
    SQLXFormsSession


@mock.patch.object(SQLXFormsSession, 'by_session_id',
                   lambda session_id: FakeSession.by_session_id(session_id))
def test_session_synchronization():
    phone_number_a = _clean_up_number('15555555555')
    phone_number_b = _clean_up_number('15555555554')
    session_a_1 = FakeSession(session_id=str(uuid4()), phone_number=phone_number_a, connection_id='Alpha')
    session_a_2 = FakeSession(session_id=str(uuid4()), phone_number=phone_number_a, connection_id='Beta')
    session_b_1 = FakeSession(session_id=str(uuid4()), phone_number=phone_number_b, connection_id='Kappa')

    # Nothing set yet, so it can be claimed
    assert XFormsSessionSynchronization.channel_is_available_for_session(session_a_1)
    # And so can the other one
    assert XFormsSessionSynchronization.channel_is_available_for_session(session_a_2)
    # Claim succeeds
    assert XFormsSessionSynchronization.claim_channel_for_session(session_a_1)
    # Claim for same channel fails
    assert not XFormsSessionSynchronization.channel_is_available_for_session(session_a_2)
    assert not XFormsSessionSynchronization.claim_channel_for_session(session_a_2)
    # But same session can re-claim it
    assert XFormsSessionSynchronization.claim_channel_for_session(session_a_1)
    # And another session can claim another channel
    assert XFormsSessionSynchronization.claim_channel_for_session(session_b_1)
    # And if the first session releases the channel
    XFormsSessionSynchronization.release_channel_for_session(session_a_1)
    # Then the contact is still set
    assert XFormsSessionSynchronization.get_running_session_info_for_channel(
        SMSChannel(BACKEND_ID, phone_number_a)
    ).contact_id == 'Alpha'
    # But the other session (that couldn't before) can claim it now
    assert XFormsSessionSynchronization.claim_channel_for_session(session_a_2)
    # Trying to clear the channel claim will fail because the session is still open
    assert not XFormsSessionSynchronization.clear_stale_channel_claim(SMSChannel(BACKEND_ID, phone_number_a))
    # But if we close the session first
    session_a_2.close()
    # The session is now "stale" so we can clear that stale channel claim
    assert XFormsSessionSynchronization.clear_stale_channel_claim(SMSChannel(BACKEND_ID, phone_number_a))
    # If we try to clear it again it'll be a no-op and return false, since it's already cleared
    assert not XFormsSessionSynchronization.clear_stale_channel_claim(SMSChannel(BACKEND_ID, phone_number_a))


@mock.patch.object(SQLXFormsSession, 'by_session_id',
                   lambda session_id: FakeSession.by_session_id(session_id))
def test_auto_clear_stale_session_on_claim():
    phone_number_a = _clean_up_number('15555555555')
    session_a_1 = FakeSession(session_id=str(uuid4()), phone_number=phone_number_a, connection_id='Alpha')
    session_a_2 = FakeSession(session_id=str(uuid4()), phone_number=phone_number_a, connection_id='Beta')

    # Nothing set yet, so it can be claimed
    assert XFormsSessionSynchronization.channel_is_available_for_session(session_a_1)
    # And so can the other one
    assert XFormsSessionSynchronization.channel_is_available_for_session(session_a_2)
    # Claim succeeds
    assert XFormsSessionSynchronization.claim_channel_for_session(session_a_1)
    # Claim for same channel fails
    assert not XFormsSessionSynchronization.channel_is_available_for_session(session_a_2)
    assert not XFormsSessionSynchronization.claim_channel_for_session(session_a_2)
    # Set the current active session to closed manually, leaving a dangling/stale session claim
    session_a_1.session_is_open = False
    # Claim for the channel now succeeds
    assert XFormsSessionSynchronization.channel_is_available_for_session(session_a_2)
    assert XFormsSessionSynchronization.claim_channel_for_session(session_a_2)
    # And it is now the active session for the channel
    assert (
        XFormsSessionSynchronization.get_running_session_info_for_channel(session_a_2.get_channel()).session_id
        == session_a_2.session_id
    )


class FakeSession:
    expire_after = 60
    _global_objects = {}

    def __init__(self, session_id, phone_number, connection_id, session_is_open=True):
        self.session_id = session_id
        self.phone_number = phone_number
        self.connection_id = connection_id
        self.session_is_open = session_is_open
        self._global_objects[session_id] = self

    def get_channel(self):
        return SMSChannel(BACKEND_ID, self.phone_number)

    def close(self):
        self.session_is_open = False

    @classmethod
    def by_session_id(cls, session_id):
        return cls._global_objects[session_id]


def _clean_up_number(phone_number):
    XFormsSessionSynchronization._set_running_session_info_for_channel(
        SMSChannel(BACKEND_ID, phone_number), RunningSessionInfo(None, None),
        expiry=10
    )
    return phone_number


BACKEND_ID = '2b00042f7481c7b056c4b410d28f33cf'


def test_pickle_roundtrip():
    assert pickle.loads(pickle.dumps(SMSChannel('abc', '123'))) == SMSChannel('abc', '123')
    assert pickle.loads(pickle.dumps(RunningSessionInfo('xxx', 'yyy'))) == RunningSessionInfo('xxx', 'yyy')
