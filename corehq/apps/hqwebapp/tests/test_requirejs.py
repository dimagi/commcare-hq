from __future__ import absolute_import
from __future__ import unicode_literals
import json
import os
import re
import subprocess

from django.test import SimpleTestCase


class TestRequireJS(SimpleTestCase):

    def setUp(self):
        super(TestRequireJS, self).setUp()
        self.prefix = os.path.join(os.getcwd(), 'corehq')

        proc = subprocess.Popen(["find", self.prefix, "-name", "*.js"], stdout=subprocess.PIPE)
        (out, err) = proc.communicate()
        self.js_files = [f for f in out.split("\n") if f
                    and not re.search(r'/_design/', f)
                    and not re.search(r'couchapps', f)
                    and not re.search(r'/vellum/', f)]

        self.hqdefine_files = []
        self.requirejs_files = []
        for filename in self.js_files:
            proc = subprocess.Popen(["grep", "^\s*hqDefine", filename], stdout=subprocess.PIPE)
            (out, err) = proc.communicate()
            if out:
                self.hqdefine_files.append(filename)
                proc = subprocess.Popen(["grep", "hqDefine.*,.*\[", filename], stdout=subprocess.PIPE)
                (out, err) = proc.communicate()
                if out:
                    self.requirejs_files.append(filename)


    def test_files_match_modules(self):
        errors = []
        for filename in self.hqdefine_files:
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

    def test_requirejs_disallows_hqimport(self):
        errors = []
        for filename in self.requirejs_files:
            # Special case 1: ignore standard_hq_report.js until we migrate UCRs and reports
            if filename.endswith("reports/js/standard_hq_report.js"):
                continue
            # Special case 2: knockout_bindings should be broken up, in the meantime, ignore
            if filename.endswith("hqwebapp/js/knockout_bindings.ko.js"):
                continue

            proc = subprocess.Popen(["grep", "hqImport", filename], stdout=subprocess.PIPE)
            (out, err) = proc.communicate()
            for line in out.split("\n"):
                if line:
                    match = re.search(r'hqImport\([\'"]([^\'"]*)[\'"]', line)
                    if match:
                        errors.append("{} imported in {}".format(match.group(1), filename))
                    else:
                        errors.append("hqImport found in {}: {}".format(filename, line.strip()))

        if errors:
            self.fail("hqImport used in RequireJS modules: \n{}".format("\n".join(errors)))

    def test_js_tests_are_comprehensive(self):
        proc = subprocess.Popen(["find", self.prefix, "-name", "*.html"], stdout=subprocess.PIPE)
        (out, err) = proc.communicate()
        html_files = [f for f in out.split("\n") if f
                      and not re.search(r'/tests/', f)]

        filename = os.path.abspath(os.path.join(os.path.dirname(__file__), '..',
                                   'static', 'hqwebapp', 'spec', 'requirejs_main.json'))
        errors = []
        with open(filename, 'r') as f:
            tested_modules = json.loads(f.read())
            for filename in html_files:
                proc = subprocess.Popen(["grep", "requirejs_main", filename], stdout=subprocess.PIPE)
                (out, err) = proc.communicate()
                for line in out.split("\n"):
                    match = re.search(r'{% requirejs_main ["\'](.*)["\'] %}', line)
                    if match:
                        module = match.group(1)
                        if module not in tested_modules:
                            errors.append(module)

        if errors:
            self.fail("Please add to requirejs_main.json: \n{}".format("\n".join(errors)))
