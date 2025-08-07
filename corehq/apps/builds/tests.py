import pytest

from corehq.apps.builds.utils import extract_build_info_from_filename


def test_extract_build_info_from_filename():
    info = extract_build_info_from_filename(
        'attachment; filename=CommCare_CommCare_2.13_32703_artifacts.zip'
    )
    assert info == ('2.13', 32703)


def test_extract_build_info_from_filename_error():
    msg = r"Could not find filename like 'CommCare_CommCare_.+_artifacts.zip' in 'foo'"
    with pytest.raises(ValueError, match=msg):
        extract_build_info_from_filename('foo')
