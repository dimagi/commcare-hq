from __future__ import absolute_import
from __future__ import unicode_literals
import re
from django.template.loader import render_to_string


class FixtureUploadResult(object):
    """
    Helper structure for handling the results of a fixture upload.
    """

    def __init__(self):
        self.success = True
        self.messages = []
        self.errors = []
        self.number_of_fixtures = 0

    def get_display_message(self):
        message = render_to_string('fixtures/partials/fixture_upload_status_api.txt', {
            'result': self,
        })
        message = '\n'.join(re.split(r'\n*', message)).strip()
        return message
