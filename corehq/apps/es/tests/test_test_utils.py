from django.test import SimpleTestCase
from testil import assert_raises, eq

from .utils import es_test, es_test_attr, temporary_index
from ..client import ElasticManageAdapter
from ..exceptions import ESRegistryError
from ..registry import (
    get_registry,
    verify_registered,
)


class MetaInfo:

    def __init__(self, name):
        self.alias = name


CATS = MetaInfo("cats")
DOGS = MetaInfo("dogs")
PIGS = MetaInfo("pigs")


@es_test
class TestNoSetup(SimpleTestCase):

    def test_no_indices_registered(self):
        with self.assertRaises(AttributeError):
            self._indices


@es_test(index=CATS)
class TestSetupIndex(SimpleTestCase):

    def test_index_registered(self):
        self.assertEqual(list(self._indices.values()), [CATS])


@es_test(indices=[CATS, DOGS])
class TestSetupIndices(SimpleTestCase):

    def test_indices_registered(self):
        verify_registered(DOGS)
        verify_registered(CATS)


@es_test(index=CATS, setup_class=True)
class TestSetupClass(SimpleTestCase):

    def test_class_indices_registered(self):
        self.assertEqual(list(self.__class__._indices.values()), [CATS])


@es_test(index=CATS, setup_class=True)
class BaseSetupTeardownCatsClass(SimpleTestCase):

    state_log = []

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.state_log.append("class_up")

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.state_log.append("class_down")


class TestSetupTeardownClassDecoratedAndCalled(BaseSetupTeardownCatsClass):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        # non-standard: test that the class is torn down
        with assert_raises(ESRegistryError):
            verify_registered(CATS)
        eq(cls.state_log, ["class_up", "class_down"])

    def test_class_is_setup(self):
        verify_registered(CATS)
        self.assertEqual(self.state_log, ["class_up"])


@es_test(index=CATS)
class TestSetupTeardownDecoratedAndCalled(SimpleTestCase):

    state_log = []

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        # non-standard: test that the instance is torn down
        with assert_raises(ESRegistryError):
            verify_registered(CATS)
        eq(cls.state_log, ["instance_up", "instance_down"])

    def setUp(self):
        super().setUp()
        self.state_log.append("instance_up")

    def tearDown(self):
        super().tearDown()
        self.state_log.append("instance_down")

    def test_instance_is_setup(self):
        verify_registered(CATS)
        self.assertEqual(self.state_log, ["instance_up"])


class TestPartialESTest(SimpleTestCase):

    @es_test_attr
    def test_no_pet_indices_registered(self):
        infos = get_registry().values()
        self.assertNotIn(CATS, infos)
        self.assertNotIn(DOGS, infos)
        self.assertNotIn(PIGS, infos)

    @es_test(index=CATS)
    def test_only_cat_indices_registered(self):
        verify_registered(CATS)
        with self.assertRaises(ESRegistryError):
            verify_registered(DOGS)

    @es_test(index=DOGS)
    def test_only_dog_indices_registered(self):
        verify_registered(DOGS)
        with self.assertRaises(ESRegistryError):
            verify_registered(CATS)


@es_test_attr
def test_registry_state_with_function_decorator():

    @es_test(index=PIGS)
    def test_pig_index_registered():
        verify_registered(PIGS)

    def test_pig_index_not_registered():
        with assert_raises(ESRegistryError):
            verify_registered(PIGS)

    yield test_pig_index_registered,
    yield test_pig_index_not_registered,


@es_test(index=PIGS, setup_class=True)
class TestNoSetupTeardownMethods:

    def test_test_instantiation_should_not_raise_attributeerror(self):
        pass


@es_test_attr
def test_setup_class_expects_classmethods():

    with assert_raises(ValueError):

        @es_test(index=PIGS, setup_class=True)
        class TestMissingClassmethods:

            def setUpClass(self):
                pass


@es_test_attr
def test_teardown_class_expects_classmethods():

    with assert_raises(ValueError):

        @es_test(index=PIGS, setup_class=True)
        class TestMissingClassmethods:

            def tearDownClass(self):
                pass


@es_test
def test_temporary_index():
    manager = ElasticManageAdapter()
    index = "test_index"

    def test_temporary_index_with_args(*args):
        with temporary_index(index, *args):
            assert manager.index_exists(index)
        assert not manager.index_exists(index)

    yield test_temporary_index_with_args,  # without type/mapping
    yield test_temporary_index_with_args, "test_doc", {}  # with type/mapping


@es_test
def test_temporary_index_fails_with_invalid_args():
    manager = ElasticManageAdapter()
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
