from django.test import SimpleTestCase
from testil import assert_raises
from unittest.mock import patch

from .utils import TestDocumentAdapter, es_test, es_test_attr, temporary_index
from ..client import manager


def test_no_setup():
    test = es_test(TestSimpleTestCase)()
    with patch.object(manager, "index_create") as mock:
        test.setUp()
    mock.assert_not_called()
    test.tearDown()


def test_no_teardown():
    test = es_test(TestSimpleTestCase)()
    test.setUp()
    with patch.object(manager, "index_delete") as mock:
        test.tearDown()
    mock.assert_not_called()


def test_no_class_setup():
    Test = es_test(TestSimpleTestCase)
    with patch.object(manager, "index_create") as mock:
        Test.setUpClass()
    mock.assert_not_called()
    Test.tearDownClass()


def test_no_class_teardown():
    Test = es_test(TestSimpleTestCase)
    Test.setUpClass()
    with patch.object(manager, "index_delete") as mock:
        Test.tearDownClass()
    mock.assert_not_called()


class TestSimpleTestCase(SimpleTestCase):
    """Use a subclass of ``SimpleTestCase`` for making discrete calls to
    {setUp,tearDown}Class so we can't break other tests if we use it in a
    non-standard way.
    """


cats_adapter = TestDocumentAdapter("cats", "cat")
dogs_adapter = TestDocumentAdapter("dogs", "dog")
pigs_adapter = TestDocumentAdapter("pigs", "pig")


def test_setup_teardown_index():

    @es_test(requires=[pigs_adapter])
    class Test(SimpleTestCase):
        def test_index_exists(self):
            assert_index_exists(pigs_adapter)

    assert_not_index_exists(pigs_adapter)
    test = Test()
    test.setUp()
    test.test_index_exists()
    test.tearDown()
    assert_not_index_exists(pigs_adapter)


def test_setup_teardown_class_index():

    @es_test(requires=[pigs_adapter], setup_class=True)
    class Test(SimpleTestCase):
        def test_index_exists(self):
            assert_index_exists(pigs_adapter)

    assert_not_index_exists(pigs_adapter)
    Test.setUpClass()
    Test().test_index_exists()
    Test.tearDownClass()
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


@es_test(requires=[cats_adapter], setup_class=True)
class TestNoSetupTeardownMethods:

    def test_test_instantiation_should_not_raise_attributeerror(self):
        """Tests that custom test case classes which lack setup and teardown
        methods do not raise an AttributeError
        """


@es_test_attr
def test_setup_class_expects_classmethod():
    try:
        @es_test(requires=[pigs_adapter], setup_class=True)
        class TestExpectsClassmethod:

            def setUpClass(self):
                pass

        assert False, "ValueError not raised"
    except ValueError as exc:
        assert str(exc).startswith("'setup_class' expects a classmethod"), str(exc)


@es_test_attr
def test_teardown_class_expects_classmethod():
    try:
        @es_test(requires=[pigs_adapter], setup_class=True)
        class TestExpectsClassmethod:

            def tearDownClass(self):
                pass

        assert False, "ValueError not raised"
    except ValueError as exc:
        assert str(exc).startswith("'setup_class' expects a classmethod"), str(exc)


@es_test
def test_temporary_index():
    index = "test_index"

    def test_temporary_index_with_args(*args):
        with temporary_index(index, *args):
            assert manager.index_exists(index)
        assert not manager.index_exists(index)

    yield test_temporary_index_with_args,  # without type/mapping
    yield test_temporary_index_with_args, "test_doc", {}  # with type/mapping


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
