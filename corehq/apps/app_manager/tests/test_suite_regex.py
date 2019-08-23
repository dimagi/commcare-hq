# -*- coding: utf-8 -*-
from django.test import SimpleTestCase
from corehq.apps.app_manager.exceptions import CaseXPathValidationError
from corehq.apps.app_manager.xpath import (
    dot_interpolate,
    UserCaseXPath,
    interpolate_xpath,
)


class RegexTest(SimpleTestCase):

    def test_regex(self):
        replacement = "@case_id stuff"
        cases = [
            ('./lmp < 570.5', '%s/lmp < 570.5'),
            ('stuff ./lmp < 570.', 'stuff %s/lmp < 570.'),
            ('.53 < hello.', '.53 < hello%s'),
            ('./name + ", Jr."', '%s/name + ", Jr."'),
            ("./name + ', Jr.'", "%s/name + ', Jr.'"),
            ("'a.b' > .", "'a.b' > %s"),
            ("\"it's a dot .\" > .", "\"it's a dot .\" > %s"),
            ("\"it's a \\\"dot\\\" .\" > .", "\"it's a \\\"dot\\\" .\" > %s"),
        ]
        for case in cases:
            self.assertEqual(
                dot_interpolate(case[0], replacement),
                case[1] % replacement
            )

    def test_interpolate_xpath(self):
        replacements = {
            'case': "<casedb stuff>",
            'user': UserCaseXPath().case(),
            'session': "instance('commcaresession')/session",
        }
        cases = [
            ('./lmp < 570.5', '{case}/lmp < 570.5'),
            ('#case/lmp < 570.5', '{case}/lmp < 570.5'),
            ('stuff ./lmp < 570.', 'stuff {case}/lmp < 570.'),
            ('stuff #case/lmp < 570.', 'stuff {case}/lmp < 570.'),
            ('.53 < hello.', '.53 < hello{case}'),
            ('.53 < hello#case', '.53 < hello{case}'),
            ('#session/data/username', '{session}/data/username'),
            ('"jack" = #session/username', '"jack" = {session}/username'),
            ('./@case_id = #session/userid', '{case}/@case_id = {session}/userid'),
            ('#case/@case_id = #user/@case_id', '{case}/@case_id = {user}/@case_id'),
            ('#host/foo = 42', "instance('casedb')/casedb/case[@case_id={case}/index/host]/foo = 42"),
            ("'ham' = #parent/spam", "'ham' = instance('casedb')/casedb/case[@case_id={case}/index/parent]/spam"),
        ]
        for case in cases:
            self.assertEqual(
                interpolate_xpath(case[0], replacements['case']),
                case[1].format(**replacements)
            )

    def test_interpolate_xpath_error(self):
        for case in ('./lmp < 570.5', '#case/lmp < 570.5'):
            with self.assertRaises(CaseXPathValidationError):
                interpolate_xpath(case, None),
