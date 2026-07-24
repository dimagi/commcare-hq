import pytest
from django.core.exceptions import ValidationError

from corehq.apps.builds.models import validate_semantic_version


@pytest.mark.parametrize("version", [
    "1.0.0",
    "2.13.0",
    "10.20.30",
    "0.0.0",
])
def test_valid_versions(version):
    assert validate_semantic_version(version) is None


@pytest.mark.parametrize("version, description", [
    ("1.0", "too few parts"),
    ("1.0.0.0", "too many parts"),
    ("1.0.a", "non-numeric patch"),
    ("a.0.0", "non-numeric major"),
    ("1.0.0-beta", "suffix on patch"),
    ("", "empty string"),
    ("1..0", "empty minor"),
    ("no_dots", "no dots at all"),
])
def test_invalid_versions(version, description):
    with pytest.raises(ValidationError):
        validate_semantic_version(version)
