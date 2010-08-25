from django.db import connection
from django.conf import settings

from xformmanager.manager import XFormManager
from xformmanager.tests.util import clear_data, create_xsd_and_populate, populate
from xformmanager.models import FormDefModel, Metadata, ElementDefModel
from domain.models import Domain

from decimal import Decimal
from datetime import datetime, date, time
import unittest
from corehq.util.dbutils import is_realsql, is_configured_realsql, is_configured_mysql

class BasicTestCase(unittest.TestCase):
    
    def setUp(self):
        clear_data()
        mockdomain = Domain.objects.get_or_create(name='dupe_dom')[0]
        self.domain = mockdomain
    
        
    def testDuplicateTag(self):
        form = create_xsd_and_populate("data/duplicate_tag.xsd", "data/duplicate_tag.xml", self.domain)
        self.assertEqual(self.domain, form.domain)
        self.assertTrue(self.domain.name in form.table_name)
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM %s" % form.form_name)
        row = cursor.fetchone()
        self.assertEquals(row[len(row) - 2],"y")
        