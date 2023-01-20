from django.test import SimpleTestCase
from nose.tools import assert_raises_regex
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
def test_index_state_with_function_decorator():

    @es_test(requires=[pigs_adapter])
    def test_pig_index_exists():
        assert_index_exists(pigs_adapter)

    def test_pig_index_does_not_exist():
        assert_not_index_exists(pigs_adapter)

    yield test_pig_index_exists,
    yield test_pig_index_does_not_exist,


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
    with assert_raises_regex(ValueError, "^'setup_class' expects a classmethod"):
        @es_test(requires=[pigs_adapter], setup_class=True)
        class TestExpectsClassmethod:
            def setUpClass(self):
                pass


@es_test
def test_temporary_index():
    index = "test_index"

    def test_temporary_index_with_args(*args):
        with temporary_index(index, *args):
            assert manager.index_exists(index)
        assert not manager.index_exists(index)

    yield test_temporary_index_with_args,  # without type/mapping
    yield test_temporary_index_with_args, "test_doc", {"_meta": {}}  # with type/mapping


@es_test
def test_temporary_index_fails_with_invalid_args():
    index = "test_index"

    def test_temporary_index_with_args(type_, mapping):
        index_was_present = manager.index_exists(index)
        with assert_raises(ValueError):
            with temporary_index(index, type_, mapping):
                pass
        assert index_was_present == manager.index_exists(index), \
            "unexpected index existence change"

    no_mapping = ("test_doc", None)
    no_type = (None, {})

    with temporary_index(index):
        # test while index exists
        assert manager.index_exists(index)
        yield test_temporary_index_with_args, *no_mapping
        yield test_temporary_index_with_args, *no_type
    # test while index does not exist
    assert not manager.index_exists(index)
    yield test_temporary_index_with_args, *no_mapping
    yield test_temporary_index_with_args, *no_type
