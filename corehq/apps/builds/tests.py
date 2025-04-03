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


# NOTE: Don't run the test below because GitHub rate-limits unauthenticated API
# request _very_ fast.
#
# See doctest in: corehq/apps/builds/management/commands/add_commcare_build.py
#
# def test_doctests():
#     import doctest
#     from .management.commands import add_commcare_build
#     results = doctest.testmod(add_commcare_build, optionflags=doctest.ELLIPSIS)
#     assert results.failed == 0, results
