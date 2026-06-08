from corehq.apps.tombstones.models import SLUG_BY_MODEL


def test_slugs_are_unique():
    slugs = list(SLUG_BY_MODEL.values())
    assert len(slugs) == len(set(slugs)), f"Duplicate slugs in SLUG_BY_MODEL: {slugs}"
