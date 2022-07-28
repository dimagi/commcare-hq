import doctest
from nose.tools import assert_equal
import corehq.util.string
from corehq.util.string import slash_join


def test_doctests():
    results = doctest.testmod(corehq.util.string)
    assert_equal(results.failed, 0)


def test_middle_strings():
    result = slash_join('http://example.com', '/foo/', 'bar/', '/baz')
    assert_equal(result, 'http://example.com/foo/bar/baz')


def test_multiple_slashes():
    result = slash_join('http://example.com', 'foo//', '//bar//')
    assert_equal(result, 'http://example.com/foo/bar//')
