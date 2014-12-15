from datetime import datetime, date
from unittest import TestCase

from couchforms.models import XFormInstance
from dimagi.utils.dates import add_months

from ..constants import *
from .case_reports import Report, OPMCase, MockCaseRow


def make_child2_form(form):
    def convert_node(node):
        if isinstance(node, dict):
            new_node = {}
            for k, v in node.items():
                new_node[k.replace('1', '2')] = convert_node(v)
            return new_node
        return node
    form.form = convert_node(form.form)
    return form


class TestMultipleChildren(TestCase):
    def setUp(self):
        self.report = Report(month=7, year=2014, block="Atri")
        self.case = OPMCase(
            forms=[],
            dod=date(2014, 1, 10),
            live_birth_amount=2,
        )
        self.row = MockCaseRow(self.case, self.report)
        self.rows = [self.row] + self.report._extra_row_objects

    def test_adds_extra_children(self):
        self.assertEqual(len(self.rows), 2)

    def test_additional_children(self):
        def check_property(prop):
            if getattr(self.row, prop) is not None:
                for row in self.report._extra_row_objects:
                    msg = ("%s applies to child1 but is not being "
                           "calculated for other children" % prop)
                    value = getattr(self.row, prop)
                    self.assertNotEqual(value, None, msg)
        child_properties = [
            'child_attended_vhnd',
            'child_growth_calculated',  # tested in test_child_conditions
            'child_received_ors',  # tested in test_child_conditions
            'child_weighed_once',  # tested in test_child_condition_four
            'child_birth_registered',  # tested in test_child_condition_four
            'child_received_measles_vaccine',  # tested in test_child_condition_four
            'child_condition_four',
            'child_breastfed',  # tested in test_child_conditions
        ]
        map(check_property, child_properties)
