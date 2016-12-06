import json
import os
import tempfile

import requests
from django.test import SimpleTestCase
from requests.auth import HTTPDigestAuth

from corehq.apps.app_manager.models import Application


class TestRealBuild(SimpleTestCase):
    @property
    def username(self):
        return os.environ['TRAVIS_HQ_USERNAME']

    @property
    def password(self):
        return os.environ['TRAVIS_HQ_PASSWORD']

    def fetch_and_build_app(self, domain, app_id):
        source_path = os.path.join(tempfile.gettempdir(), '{}.{}.json'.format(domain, app_id))
        if os.path.isfile(source_path):
            with open(source_path, 'r') as f:
                app_source = json.load(f)
        else:
            url = "https://www.commcarehq.org/a/{}/apps/source/{}/".format(
                domain, app_id
            )
            response = requests.get(url, auth=HTTPDigestAuth(self.username, self.password))
            response.raise_for_status()
            with open(source_path, 'w') as f:
                app_source = response.json()
                json.dump(app_source, f)

        app = Application.wrap(app_source)
        app.create_all_files()

    def test_real_build(self):
        self.fetch_and_build_app('adra-asotry-spce', '7c162ad69c378e7e47c0a5aa4531d277')
