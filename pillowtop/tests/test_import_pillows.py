from django.test import override_settings, SimpleTestCase
from pillowtop import get_all_pillow_instances, get_all_pillow_classes, get_pillow_by_name
from pillowtop.checkpoints.manager import PillowCheckpoint
from pillowtop.dao.mock import MockDocumentStore
from pillowtop.feed.mock import RandomChangeFeed
from pillowtop.listener import BasicPillow
from inspect import isclass
from pillowtop.pillow.interface import ConstructedPillow


class FakePillow(BasicPillow):
    _couch_db = object()  # hack to make tests pass since this is required


@override_settings(PILLOWTOPS={'test': ['pillowtop.tests.FakePillow']})
class PillowImportTestCase(SimpleTestCase):

    def test_get_pillow_classes(self):
        pillows = get_all_pillow_classes()
        self.assertEquals(len(pillows), 1)
        self.assertTrue(isclass(pillows[0]))

    def test_get_pillow_instances(self):
        pillows = get_all_pillow_instances()
        self.assertEquals(len(pillows), 1)
        self.assertFalse(isclass(pillows[0]))

    def test_get_pillow_by_name(self):
        self.assertEqual(FakePillow, type(get_pillow_by_name('FakePillow')))


class FakeConstructedPillow(ConstructedPillow):

    def processor(self, change, do_set_checkpoint=True):
        pass


def make_fake_constructed_pillow():
    fake_dao = MockDocumentStore()
    pillow = FakeConstructedPillow(
        document_store=fake_dao,
        checkpoint=PillowCheckpoint(fake_dao, 'fake-constructed-pillow'),
        change_feed=RandomChangeFeed(10)
    )
    return pillow


PILLOWTOPS_OVERRIDE = {
    'test': [
        {
            'class': 'pillowtop.tests.FakeConstructedPillow',
            'instance': 'pillowtop.tests.make_fake_constructed_pillow'
        }
    ]
}

@override_settings(PILLOWTOPS=PILLOWTOPS_OVERRIDE)
class PillowFactoryFunctionTestCase(SimpleTestCase):

    def test_get_pillow_classes(self):
        pillows = get_all_pillow_classes()
        self.assertEquals(len(pillows), 1)
        pillow_class = pillows[0]
        self.assertTrue(isclass(pillow_class))
        self.assertEqual(FakeConstructedPillow, pillow_class)

    def test_import_pillows(self):
        pillows = get_all_pillow_instances()
        self.assertEquals(len(pillows), 1)
        pillow = pillows[0]
        self.assertFalse(isclass(pillow))
        self.assertEqual(FakeConstructedPillow, type(pillow))
