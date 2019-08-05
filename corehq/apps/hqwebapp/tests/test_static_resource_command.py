from __future__ import absolute_import
from __future__ import unicode_literals
import os
import yaml

from django.test import SimpleTestCase
from corehq.apps.hqwebapp.management.commands.resource_static import Command as ResourceStaticCommand
from get_resource_versions import get_resource_versions


class TestResourceStatic(SimpleTestCase):
    @classmethod
    def resource_versions_filename(cls):
        return os.path.join(os.path.dirname(__file__), 'data', 'resource_versions.yaml')

    def setUp(self):
        super(TestResourceStatic, self).setUp()
        with open(self.resource_versions_filename(), 'r') as f:
            self.original_resources = yaml.safe_load(f)

    def tearDown(self):
        super(TestResourceStatic, self).tearDown()
        with open(self.resource_versions_filename(), 'w') as f:
            f.write(yaml.dump(self.original_resources))

    def get_resource_versions(self):
        resource_versions = get_resource_versions(path=self.resource_versions_filename())
        self.assertEquals(resource_versions, {
            'somefile.js': '123abc',
        })

    def test_output_resources(self):
        ResourceStaticCommand().output_resources({
            'anotherfile.js': '890xyz',
        }, overwrite=False, path=self.resource_versions_filename())
        resource_versions = get_resource_versions(path=self.resource_versions_filename())
        self.assertEquals(resource_versions, {
            'somefile.js': '123abc',
            'anotherfile.js': '890xyz',
        })

    def test_output_resources_with_overwrite(self):
        ResourceStaticCommand().output_resources({
            'anotherfile.js': '890xyz',
        }, overwrite=True, path=self.resource_versions_filename())
        resource_versions = get_resource_versions(path=self.resource_versions_filename())
        self.assertEquals(resource_versions, {
            'anotherfile.js': '890xyz',
        })
