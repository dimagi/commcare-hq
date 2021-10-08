from django.test import SimpleTestCase
from testil import assert_raises

from .utils import es_test, es_test_attr
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

            def tearDownClass(self):
                pass
