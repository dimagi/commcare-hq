from __future__ import absolute_import
from __future__ import unicode_literals
import os
import re
import subprocess

from django.test import SimpleTestCase


class TestRequireJS(SimpleTestCase):

    def _get_hqdefine_files(self):
        prefix = os.path.join(os.getcwd(), 'corehq')

        proc = subprocess.Popen(["find", prefix, "-name", "*.js"], stdout=subprocess.PIPE)
        (out, err) = proc.communicate()
        js_files = [f for f in out.split("\n") if f
                    and not re.search(r'/_design/', f)
                    and not re.search(r'couchapps', f)
                    and not re.search(r'/vellum/', f)]

        return js_files

    def test_files_match_modules(self):
        errors = []
        for filename in self._get_hqdefine_files():
            proc = subprocess.Popen(["grep", "hqDefine", filename], stdout=subprocess.PIPE)
            (out, err) = proc.communicate()
            for line in out.split("\n"):
                match = re.search(r'^\s*hqDefine\([\'"]([^\'"]*)[\'"]', line)
                if match:
                    module = match.group(1)
                    if not filename.endswith(module + ".js"):
                        errors.append("Module {} defined in file {}".format(module, filename))

        if errors:
            self.fail("Mismatched JS file/modules: \n{}".format("\n".join(errors)))
