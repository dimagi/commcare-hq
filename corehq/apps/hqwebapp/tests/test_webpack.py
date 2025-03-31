import subprocess

from django.test import SimpleTestCase


class TestWebpack(SimpleTestCase):
    def test_webpack_build(self):
        proc = subprocess.Popen(["yarn", "build"], stdout=subprocess.PIPE)
        (out, err) = proc.communicate()
        if proc.returncode:
            self.fail(out)
