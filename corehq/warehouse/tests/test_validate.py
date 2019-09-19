from corehq.warehouse.const import ALL_TABLES
from corehq.warehouse.loaders import get_loader_by_slug


def test_validate_loaders():
    for slug in ALL_TABLES:
        loader = get_loader_by_slug(slug)
        loader().validate()
