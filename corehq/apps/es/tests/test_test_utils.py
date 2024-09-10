import re
from contextlib import nullcontext

import pytest
from django.test import SimpleTestCase
from testil import assert_raises
from unittest.mock import patch

from .utils import TestDocumentAdapter, es_test, es_test_attr, temporary_index
from ..client import manager


class TestSetupAndCleanups(SimpleTestCase):

    class TestSimpleTestCase(SimpleTestCase):
        """Use a subclass of ``SimpleTestCase`` for making discrete calls to
        setUp[Class]/do[Class]Cleanups so we can't break other tests if we use it
        in a non-standard way.
        """

    def test_no_setup(self):
        test = es_test(self.TestSimpleTestCase)()
        with patch.object(manager, "index_create") as mock:
            test.setUp()
        mock.assert_not_called()

    def test_no_cleanups(self):
        test = es_test(self.TestSimpleTestCase)()
        test.setUp()
        with patch.object(manager, "index_delete") as mock:
            test.tearDown()
            test.doCleanups()
        mock.assert_not_called()

    def test_no_class_setup(self):
        Test = es_test(self.TestSimpleTestCase)
        with patch.object(manager, "index_create") as mock:
            Test.setUpClass()
        mock.assert_not_called()
        Test.tearDownClass()
        Test.doClassCleanups()

    def test_no_class_cleanups(self):
        Test = es_test(self.TestSimpleTestCase)
        Test.setUpClass()
        with patch.object(manager, "index_delete") as mock:
            Test.tearDownClass()
            Test.doClassCleanups()
        mock.assert_not_called()


cats_adapter = TestDocumentAdapter("cats", "cat")
dogs_adapter = TestDocumentAdapter("dogs", "dog")
pigs_adapter = TestDocumentAdapter("pigs", "pig")


def test_setup_tolerates_existing_index():

    @es_test(requires=[cats_adapter])
    class TestCatsRequired(SimpleTestCase):
        def test_index_exists(self):
            assert_index_exists(cats_adapter)

    dirty_test = TestCatsRequired()
    dirty_test.setUp()
    dirty_test.test_index_exists()
    # dirty test never cleans up
    tolerant_test = TestCatsRequired()
    tolerant_test.setUp()  # does not raise "index_already_exists_exception"
    tolerant_test.test_index_exists()
    tolerant_test.tearDown()
    tolerant_test.doCleanups()
    # tolerant test still cleans up
    assert_not_index_exists(cats_adapter)


def test_setup_cleanup_index():

    @es_test(requires=[pigs_adapter])
    class Test(SimpleTestCase):
        def test_index_exists(self):
            assert_index_exists(pigs_adapter)

    assert_not_index_exists(pigs_adapter)
    test = Test()
    test.setUp()
    test.test_index_exists()
    test.tearDown()
    test.doCleanups()
    assert_not_index_exists(pigs_adapter)


def test_setup_cleanup_class_index():

    @es_test(requires=[pigs_adapter], setup_class=True)
    class Test(SimpleTestCase):
        def test_index_exists(self):
            assert_index_exists(pigs_adapter)

    assert_not_index_exists(pigs_adapter)
    Test.setUpClass()
    Test().test_index_exists()
    Test.tearDownClass()
    Test.doClassCleanups()
    assert_not_index_exists(pigs_adapter)


class TestPartialESTest(SimpleTestCase):

    @es_test_attr
    def test_no_pet_indexes_exist(self):
        assert_not_index_exists(cats_adapter)
        assert_not_index_exists(dogs_adapter)

    @es_test(requires=[cats_adapter])
    def test_only_cat_index_exists(self):
        assert_index_exists(cats_adapter)
        assert_not_index_exists(dogs_adapter)

    @es_test(requires=[dogs_adapter])
    def test_only_dog_index_exists(self):
        assert_index_exists(dogs_adapter)
        assert_not_index_exists(cats_adapter)


@es_test_attr
@es_test(requires=[pigs_adapter])
def test_pig_index_exists():
    assert_index_exists(pigs_adapter)


@es_test_attr
def test_pig_index_does_not_exist():
    assert_not_index_exists(pigs_adapter)


def assert_index_exists(adapter):
    indexes = list(manager.get_indices())
    assert adapter.index_name in indexes, \
        f"AssertionError: {adapter.index_name!r} not found in {indexes!r}"


def assert_not_index_exists(adapter):
    indexes = list(manager.get_indices())
    assert adapter.index_name not in indexes, \
        f"AssertionError: {adapter.index_name!r} unexpectedly found in {indexes!r}"


@es_test_attr
def test_setup_class_expects_classmethod():
    with assert_raises(ValueError, msg=re.compile("^'setup_class' expects a classmethod")):
        @es_test(requires=[pigs_adapter], setup_class=True)
        class TestExpectsClassmethod:
            def setUpClass(self):
                pass


@pytest.mark.parametrize("args", [
    (),  # without type/mapping
    ("test_doc", {"_meta": {}}),  # with type/mapping
])
@es_test
def test_temporary_index(args):
    index = "test_index"
    with temporary_index(index, *args):
        assert manager.index_exists(index)
    assert not manager.index_exists(index)


@pytest.mark.parametrize("has_index, type_, mapping", [
    # test while index exists
    (True, "test_doc", None),  # no mapping
    (True, None, {}),  # no type

    # test while index does not exist
    (False, "test_doc", None),  # no mapping
    (False, None, {}),  # no type
])
@es_test
def test_temporary_index_fails_with_invalid_args(has_index, type_, mapping):
    index = "test_index"
    with (temporary_index(index) if has_index else nullcontext()):
        if has_index:
            assert manager.index_exists(index)
        else:
            assert not manager.index_exists(index)

        index_was_present = manager.index_exists(index)
        with assert_raises(ValueError):
            with temporary_index(index, type_, mapping):
                pass
        assert index_was_present == manager.index_exists(index), \
            "unexpected index existence change"
