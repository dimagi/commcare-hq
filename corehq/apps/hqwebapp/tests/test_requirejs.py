from __future__ import absolute_import
from __future__ import unicode_literals
import os
import re
import subprocess
from nose.plugins.attrib import attr

from django.test import SimpleTestCase

from django.conf import settings
from django.contrib.staticfiles import finders

class TestRequireJS(SimpleTestCase):

    def test_files_match_modules(self):
        prefix = os.path.join(os.getcwd(), 'corehq')

        proc = subprocess.Popen(["find", prefix, "-name", "*.js"], stdout=subprocess.PIPE)
        (out, err) = proc.communicate()
        js_files = [f for f in out.split("\n") if f
                                               and not re.search(r'/_design/', f)
                                               and not re.search(r'couchapps', f)
                                               and not re.search(r'/vellum/', f)]

        errors = {}
        for filename in js_files:
            proc = subprocess.Popen(["grep", "hqDefine", filename], stdout=subprocess.PIPE)
            (out, err) = proc.communicate()
            for line in out.split("\n"):
                match = re.search(r'^\s*hqDefine\([\'"]([^\'"]*)[\'"]', line)
                if match:
                    module = match.group(1)
                    if not filename.endswith(module + ".js"):
                        errors[module] = filename

        if errors:
            for module, filename in errors.items():
                print "Module {} defined in file {}".format(module, filename)
            self.fail("Mismatched JS file/modules, see output above")
