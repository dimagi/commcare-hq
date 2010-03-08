from django.db import connection, transaction, DatabaseError
from receiver.models import Submission, Attachment, SubmissionHandlingOccurrence
from xformmanager.tests.util import *

from datetime import datetime
import unittest

class RemoveTestCase(unittest.TestCase):
    
    def setUp(self):
        clear_data()
        SubmissionHandlingOccurrence.objects.all().delete()
        mockdomain = Domain.objects.get_or_create(name='remdomain')[0]
        self.domain = mockdomain
        
        
    def test1ClearFormData(self):
        """ Tests clear out all forms. """
        create_xsd_and_populate("1_basic.xsd", "1_basic.xml", self.domain)
        create_xsd_and_populate("2_types.xsd", "2_types.xml", self.domain)
        create_xsd_and_populate("3_deep.xsd", "3_deep.xml", self.domain)
        create_xsd_and_populate("4_verydeep.xsd", "4_verydeep.xml", self.domain)
        create_xsd_and_populate("5_singlerepeat.xsd", "5_singlerepeat.xml", self.domain)
        create_xsd_and_populate("6_nestedrepeats.xsd", "6_nestedrepeats.xml", self.domain)
        create_xsd_and_populate("data/pf_followup.xsd", "data/pf_followup_1.xml", self.domain)
        su = StorageUtility()
        su.clear()
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM xformmanager_formdefmodel")
        row = cursor.fetchone()
        self.assertEquals(row,None)
        cursor.execute("SELECT * FROM xformmanager_elementdefmodel")
        row = cursor.fetchone()
        self.assertEquals(row,None)
        cursor.execute("SELECT * FROM xformmanager_metadata")
        row = cursor.fetchone()
        self.assertEquals(row,None)
        if settings.DATABASE_ENGINE == 'mysql':
            cursor.execute("show tables like 'schema_remdomain_%'")
            row = cursor.fetchone()
            self.assertEquals(row,None)

    def test2RemoveSchema(self):
        """ Test removing one schema """
        schema_remdomain_model = create_xsd_and_populate("1_basic.xsd", "1_basic.xml", self.domain)
        su = StorageUtility()
        su.remove_schema(schema_remdomain_model.id)
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM xformmanager_formdefmodel")
        row = cursor.fetchone()
        self.assertEquals(row,None)
        cursor.execute("SELECT * FROM xformmanager_elementdefmodel")
        row = cursor.fetchone()
        self.assertEquals(row,None)
        if settings.DATABASE_ENGINE == 'mysql':
            cursor.execute("show tables like 'schema_remdomain_xml_basic%'")
            row = cursor.fetchone()
            self.assertEquals(row,None)
    
    def test3RemoveSchema(self):
        """ Test removing a more complicated schema """
        schema_remdomain_model = create_xsd_and_populate("6_nestedrepeats.xsd", "6_nestedrepeats.xml", self.domain)
        num_handled = SubmissionHandlingOccurrence.objects.all().count()
        self.assertEquals(1,num_handled)
        all_meta = Metadata.objects.all()
        count = all_meta.count()
        self.assertEquals(1,count)
        attachment = all_meta[0].attachment
        su = StorageUtility()
        su.remove_schema(schema_remdomain_model.id)
        # Test that children have become orphans
        num_handled = SubmissionHandlingOccurrence.objects.all().count()
        self.assertEquals(0,num_handled)
        count = Metadata.objects.all().count()
        self.assertEquals(0,count)
        self.assertTrue(attachment.submission.is_orphaned())
        # TODO fix the db call to be more standard here
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM xformmanager_formdefmodel")
        row = cursor.fetchone()
        self.assertEquals(row,None)
        cursor.execute("SELECT * FROM xformmanager_elementdefmodel")
        row = cursor.fetchone()
        self.assertEquals(row,None)
        if settings.DATABASE_ENGINE == 'mysql':
            cursor.execute("show tables like 'schema_remdomain_xml_nestedrepeats%'")
            row = cursor.fetchone()
            self.assertEquals(row,None)

    def test4DeleteInstance(self):
        """ Test instance data deletion from XFormmanager """
        formdefmodel_5 = create_xsd_and_populate("5_singlerepeat.xsd", domain=self.domain)
        instance_5 = populate("5_singlerepeat.xml", self.domain)
        formdefmodel_6 = create_xsd_and_populate("6_nestedrepeats.xsd", domain=self.domain)
        instance_6 = populate("6_nestedrepeats.xml", self.domain)
        xformmanager = XFormManager()

        num_handled = SubmissionHandlingOccurrence.objects.all().count()
        self.assertEquals(2,num_handled)
        count = Metadata.objects.all().count()
        self.assertEquals(2,count)
        
        # TODO - change this syntax once meta.attachment becomes meta.submission
        xformmanager.remove_data(formdefmodel_5.id, instance_5.xform.form_metadata.all()[0].raw_data )
        xformmanager.remove_data(formdefmodel_6.id, instance_6.xform.form_metadata.all()[0].raw_data )
        # test metadata deletion

        # Test that children have been marked as 'deleted' and are no longer 'initially handled'
        # (so that they are not considered 'orphans' i.e. unhandled)
        num_handled = SubmissionHandlingOccurrence.objects.all().count()
        self.assertEquals(2,num_handled)
        for handle_means in SubmissionHandlingOccurrence.objects.all():
            self.assertEqual("deleted", handle_means.handled.method)
        self.assertFalse(instance_5.is_orphaned())        
        self.assertFalse(instance_6.is_orphaned())        
        
        count = Metadata.objects.all().count()
        self.assertEquals(0,count)
        # test raw data deletion
        if settings.DATABASE_ENGINE == 'mysql':
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM schema_remdomain_xml_singlerepeat")
            row = cursor.fetchall()
            self.assertEquals(len(row),0)
            cursor.execute("SELECT * FROM schema_remdomain_xml_singlerepeat_root_userid")
            row = cursor.fetchone()
            self.assertEquals(row,None)
            cursor.execute("SELECT * FROM schema_remdomain_xml_nestedrepeats")
            row = cursor.fetchone()
            self.assertEquals(row,None)
            cursor.execute("SELECT * FROM schema_remdomain_xml_nestedrepeats_root_nested")
            row = cursor.fetchone()
            self.assertEquals(row,None)
        
    def test4DeleteSubmissionMetadata(self):
        """ This is more a sanity check than anything else. Makes sure
        Django deletes the entire dependency chain for Submission objects. """
        formdefmodel_5 = create_xsd_and_populate("5_singlerepeat.xsd", domain=self.domain)
        instance_5 = populate("5_singlerepeat.xml", self.domain)
        formdefmodel_6 = create_xsd_and_populate("6_nestedrepeats.xsd", domain=self.domain)
        instance_6 = populate("6_nestedrepeats.xml", self.domain)
        instance_5.delete()
        instance_6.delete()
        # receiver unit tests already check for count([Submission|Attachment]) = 0
        # so here we test for metadata deletion
        count = Metadata.objects.all().count()
        self.assertEquals(0,count)
        
    def tearDown(self):
        pass
        
