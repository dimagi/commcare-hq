import pytest

from corehq.apps.user_importer.exceptions import MobileWorkerLimitReached
from corehq.apps.user_importer.importer import MobileWorkerSlots


def test_claim_counts_down_to_limit():
    slots = MobileWorkerSlots(2)
    slots.claim()
    slots.claim()
    assert slots.remaining == 0
    with pytest.raises(MobileWorkerLimitReached):
        slots.claim()


def test_release_frees_slot():
    slots = MobileWorkerSlots(1)
    slots.claim()
    slots.release()
    slots.claim()
    assert slots.remaining == 0


def test_release_when_over_limit_does_not_free_slot():
    slots = MobileWorkerSlots(-1)
    slots.release()
    with pytest.raises(MobileWorkerLimitReached):
        slots.claim()


def test_unlimited():
    slots = MobileWorkerSlots(None)
    slots.claim()
    slots.release()
    assert slots.remaining is None
