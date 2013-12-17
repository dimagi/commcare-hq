from django.test.testcases import TestCase
from corehq.apps.receiverwrapper.signals import _get_domain, _get_app_id
from couchforms.models import XFormInstance


class UrlRegexTest(TestCase):
    def test_domain(self):
        app_id = '23a0ca2230411bbf0ad33850846fbe93'
        domains = ['domain', 'hyphen-domain', 'dot.domain']
        paths = [
            ("/a/{domain}/receiver", False),
            ("/a/{domain}/receiver/", False),
            ("/a/{domain}/receiver/{app_id}/", True),
            ("/a/{domain}/receiver/secure/{app_id}/", True),
            ("/a/{domain}/receiver/secure/", False),
        ]
        for domain in domains:
            for path, has_app_id in paths:
                path = path.format(domain=domain, app_id=app_id)
                xform = XFormInstance(path=path)
                self.assertEqual(_get_domain(xform), domain, "%s %s" % (_get_domain(xform), path))
                self.assertEqual(_get_app_id(xform), app_id if has_app_id else None, "%s %s" % (_get_app_id(xform), path))
