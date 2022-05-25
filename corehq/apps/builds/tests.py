from corehq.apps.builds.utils import extract_build_info_from_filename

# FIXME: does this do anything?
# $ ./manage.py test -v corehq/apps/builds/tests.py
# nosetests corehq/apps/builds/tests.py --verbosity=2
#
# ----------------------------------------------------------------------
# Ran 0 tests in 0.000s
#
# OK
__test__ = {
    'extract_build_info_from_filename': extract_build_info_from_filename
}

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
