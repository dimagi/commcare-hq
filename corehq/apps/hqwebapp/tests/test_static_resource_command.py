from __future__ import absolute_import
from __future__ import unicode_literals
import os
import tempfile
import yaml

from django.test import SimpleTestCase
from corehq.apps.hqwebapp.management.commands.resource_static import Command as ResourceStaticCommand
from get_resource_versions import get_resource_versions


class TestResourceStatic(SimpleTestCase):
    def setUp(self):
        super(TestResourceStatic, self).setUp()
        dummy, self.resource_versions_filename = tempfile.mkstemp(suffix='yaml')
        with open(self.resource_versions_filename, 'w') as f:
            f.write(yaml.dump([
                {
                    'name': 'somefile.js',
                    'version': '123abc',
                },
                {
                    'name': 'otherfile.js',
                    'version': '456def',
                },
            ]))

    def tearDown(self):
        super(TestResourceStatic, self).tearDown()
        os.remove(self.resource_versions_filename)

    def get_resource_versions(self):
        resource_versions = get_resource_versions(path=self.resource_versions_filename)
        self.assertEquals(resource_versions, {
            'somefile.js': '123abc',
            'otherfile.js': '456def',
        })

    def test_output_resources(self):
        ResourceStaticCommand().output_resources({
            'otherfile.js': '567tuv',
            'anotherfile.js': '890xyz',
        }, overwrite=False, path=self.resource_versions_filename)
        resource_versions = get_resource_versions(path=self.resource_versions_filename)
        self.assertEquals(resource_versions, {
            'somefile.js': '123abc',
            'anotherfile.js': '890xyz',
            'otherfile.js': '567tuv',
        })

    def test_output_resources_with_overwrite(self):
        ResourceStaticCommand().output_resources({
            'otherfile.js': '567tuv',
            'anotherfile.js': '890xyz',
        }, overwrite=True, path=self.resource_versions_filename)
        resource_versions = get_resource_versions(path=self.resource_versions_filename)
        self.assertEquals(resource_versions, {
            'otherfile.js': '567tuv',
            'anotherfile.js': '890xyz',
        })
