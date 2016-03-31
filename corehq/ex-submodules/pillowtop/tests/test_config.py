from django.test import SimpleTestCase
from pillowtop.utils import get_pillow_config_from_setting


class PillowConfigTest(SimpleTestCase):

    def test_from_string(self):
        class_name = 'my.cool.Pillow'
        config = get_pillow_config_from_setting('my-section', class_name)
        self.assertEqual('my-section', config.section)
        self.assertEqual(class_name, config.class_name)
        self.assertEqual(None, config.instance_generator)

    def test_from_dict(self):
        pillow_config = {
            'class': 'my.cool.Pillow',
            'instance': 'my.instance.method',
            'name': 'MyPillow',
        }
        config = get_pillow_config_from_setting('my-section', pillow_config)
        self.assertEqual('my-section', config.section)
        self.assertEqual(pillow_config['class'], config.class_name)
        self.assertEqual(pillow_config['instance'], config.instance_generator)
        self.assertEqual(pillow_config['name'], config.name)
