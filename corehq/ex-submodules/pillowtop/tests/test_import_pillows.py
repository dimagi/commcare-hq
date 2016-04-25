from django.test import override_settings, SimpleTestCase, TestCase
from pillowtop import get_all_pillow_instances, get_all_pillow_classes, get_pillow_by_name
from pillowtop.checkpoints.manager import PillowCheckpoint
from pillowtop.exceptions import PillowNotFoundError
from pillowtop.feed.mock import RandomChangeFeed
from pillowtop.feed.interface import Change
from pillowtop.listener import BasicPillow
from inspect import isclass
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import LoggingProcessor


class FakePillow(BasicPillow):
    pass


@override_settings(PILLOWTOPS={'test': ['pillowtop.tests.FakePillow']})
class PillowImportTestCase(SimpleTestCase):

    def test_get_all_pillow_classes(self):
        pillows = get_all_pillow_classes()
        self.assertEquals(len(pillows), 1)
        self.assertTrue(isclass(pillows[0]))

    def test_get_all_pillow_instances(self):
        pillows = get_all_pillow_instances()
        self.assertEquals(len(pillows), 1)
        self.assertFalse(isclass(pillows[0]))

    def test_get_pillow_by_name(self):
        self.assertEqual(FakePillow, get_pillow_by_name('FakePillow', instantiate=False))

    def test_get_pillow_by_name_instantiate(self):
        self.assertEqual(FakePillow, type(get_pillow_by_name('FakePillow', instantiate=True)))

    def test_get_pillow_by_name_missing(self):
        with self.assertRaises(PillowNotFoundError):
            get_pillow_by_name('MissingPillow')


class FakeConstructedPillow(ConstructedPillow):
    pass


def make_fake_constructed_pillow(pillow_id):
    pillow = FakeConstructedPillow(
        name=pillow_id,
        checkpoint=PillowCheckpoint('fake-constructed-pillow'),
        change_feed=RandomChangeFeed(10),
        processor=LoggingProcessor(),
    )
    return pillow


PILLOWTOPS_OVERRIDE = {
    'test': [
        {
            'name': 'FakeConstructedPillowName',
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

    def test_get_pillow_instances(self):
        pillows = get_all_pillow_instances()
        self.assertEquals(len(pillows), 1)
        pillow = pillows[0]
        self.assertFalse(isclass(pillow))
        self.assertEqual(FakeConstructedPillow, type(pillow))
        self.assertEqual(pillow.get_name(), 'FakeConstructedPillowName')

    def test_get_pillow_class_by_name(self):
        pillow = get_pillow_by_name('FakeConstructedPillowName', instantiate=False)
        self.assertEqual(FakeConstructedPillow, pillow)

    def test_get_pillow_by_name_instantiate(self):
        pillow = get_pillow_by_name('FakeConstructedPillowName', instantiate=True)
        self.assertFalse(isclass(pillow))
        self.assertEqual(FakeConstructedPillow, type(pillow))
        self.assertEqual(pillow.get_name(), 'FakeConstructedPillowName')


@override_settings(PILLOWTOPS=PILLOWTOPS_OVERRIDE)
class PillowTestCase(TestCase):

    def test_pillow_reset_checkpoint(self):
        pillow = make_fake_constructed_pillow('FakeConstructedPillowName')
        seq_id = '456'
        pillow.set_checkpoint(Change('123', seq_id))
        self.assertEqual(pillow.checkpoint.get_or_create_wrapped().document.sequence, seq_id)
        pillow.reset_checkpoint()
        self.assertEqual(pillow.checkpoint.get_or_create_wrapped().document.sequence, '0')
