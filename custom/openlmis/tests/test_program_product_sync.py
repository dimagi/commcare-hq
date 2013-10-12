import os
from django.test import TestCase
from corehq.apps.commtrack.tests import bootstrap_domain
from custom.openlmis.api import get_programs_and_products
from custom.openlmis.commtrack import sync_openlmis_program


TEST_DOMAIN = 'openlmis-commtrack-program-test'

class ProgramSyncTest(TestCase):

    def setUp(self):
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')
        bootstrap_domain(TEST_DOMAIN)


    def testCreateProgram(self):
        with open(os.path.join(self.datapath, 'program_products.rss')) as f:
            programs = list(get_programs_and_products(f.read()))

        lmis_program = programs[0]
        commtrack_program = sync_openlmis_program(TEST_DOMAIN, lmis_program)
        self.assertEqual(lmis_program.name, commtrack_program.name)
        self.assertEqual(lmis_program.code, commtrack_program.code)
