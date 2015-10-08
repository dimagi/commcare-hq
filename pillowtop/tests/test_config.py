from django.test import SimpleTestCase
from pillowtop.utils import get_pillow_config_from_setting


class PillowConfigTest(SimpleTestCase):

    def test_from_string(self):
        class_name = 'my.cool.Pillow'
        config = get_pillow_config_from_setting('my-section', class_name)
        self.assertEqual('my-section', config.section)
        self.assertEqual(class_name, config.class_name)
        self.assertEqual(class_name, config.instance_generator)
