from corehq.apps.tombstones.models import ModelClassField


def test_slugs_are_unique():
    slugs = list(ModelClassField()._slug_by_model.values())
    assert len(slugs) == len(set(slugs)), f"Duplicate slugs: {slugs}"
