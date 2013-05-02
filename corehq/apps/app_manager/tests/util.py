import json
import os

class TestFileMixin(object):

    file_path = ''

    @property
    def base(self):
        return os.path.join(os.path.dirname(__file__), *self.file_path)

    def get_file(self, name, ext):
        with open(os.path.join(self.base, '%s.%s' % (name, ext))) as f:
            return f.read()

    def get_json(self, name):
        return json.loads(self.get_file(name, 'json'))

    def get_xml(self, name):
        return self.get_file(name, 'xml')