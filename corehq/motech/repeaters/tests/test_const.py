import pytest

from corehq.motech.repeaters.const import STATE_GROUPS, State, states_for_key


@pytest.mark.parametrize('key, expected', [
    (None, None),
    ('', None),
    ('NOT_A_GROUP', None),
    ('PENDING', (State.Pending,)),
    ('PAYLOADERROR', (State.PayloadRejected, State.ErrorGeneratingPayload)),
    ('payloaderror', (State.PayloadRejected, State.ErrorGeneratingPayload)),
])
def test_states_for_key(key, expected):
    assert states_for_key(key) == expected


def test_every_state_belongs_to_exactly_one_group():
    grouped_states = [s for states in STATE_GROUPS.values() for s in states]
    assert sorted(grouped_states) == sorted(State)
