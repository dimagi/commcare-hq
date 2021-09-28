from collections import Counter

from ..management.commands.load_domain_data import LOADERS


def test_non_overlapping_loader_slugs():
    slugs = Counter(loader.slug for loader in LOADERS)
    [(slug, count)] = slugs.most_common(1)
    assert count == 1, f"Duplicate loader slugs found: {slug}"

    for slug in slugs:
        for other in slugs:
            if slug == other:
                continue

            assert not other.startswith(slug), f"Loader slugs most not overlap: {slug} - {other}"
