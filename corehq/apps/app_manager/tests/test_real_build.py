import os
from unittest import SkipTest

import requests
from django.test import SimpleTestCase
from requests.auth import HTTPDigestAuth

from corehq.apps.app_manager.models import Application


class TestRealBuild(SimpleTestCase):

    def fetch_and_build_app(self, domain, app_id):
        try:
            username = os.environ['TRAVIS_HQ_USERNAME']
            password = os.environ['TRAVIS_HQ_PASSWORD']
        except KeyError as err:
            if os.environ.get("TRAVIS") == "true":
                raise
            raise SkipTest("not travis (KeyError: {})".format(err))
        url = "https://www.commcarehq.org/a/{}/apps/source/{}/".format(
            domain, app_id
        )
        response = requests.get(url, auth=HTTPDigestAuth(username, password))
        response.raise_for_status()
        app = Application.wrap(response.json())
        app.create_all_files()

    def test_real_build(self):
        self.fetch_and_build_app('commcare-tests', 'ae3c6e073262360f89d2630cfd220bd3')
