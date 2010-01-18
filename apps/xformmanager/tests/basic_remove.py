from django.db import connection, transaction, DatabaseError
from receiver.models import Submission, Attachment, SubmissionHandlingOccurrence
from xformmanager.tests.util import *

from datetime import datetime
import unittest

class RemoveTestCase(unittest.TestCase):
    
    def setUp(self):
        clear_data()
        SubmissionHandlingOccurrence.objects.all().delete()
        
    def test1ClearFormData(self):
        """ Tests clear out all forms. """
        create_xsd_and_populate("1_basic.xsd", "1_basic.xml")
        create_xsd_and_populate("2_types.xsd", "2_types.xml")
        create_xsd_and_populate("3_deep.xsd", "3_deep.xml")
        create_xsd_and_populate("4_verydeep.xsd", "4_verydeep.xml")
        create_xsd_and_populate("5_singlerepeat.xsd", "5_singlerepeat.xml")
        create_xsd_and_populate("6_nestedrepeats.xsd", "6_nestedrepeats.xml")
        create_xsd_and_populate("data/pf_followup.xsd", "data/pf_followup_1.xml")
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
            cursor.execute("show tables like 'schema_%'")
            row = cursor.fetchone()
            self.assertEquals(row,None)

    def test2RemoveSchema(self):
        """ Test removing one schema """
        schema_model = create_xsd_and_populate("1_basic.xsd", "1_basic.xml")
        su = StorageUtility()
        su.remove_schema(schema_model.id)
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM xformmanager_formdefmodel")
        row = cursor.fetchone()
        self.assertEquals(row,None)
        cursor.execute("SELECT * FROM xformmanager_elementdefmodel")
        row = cursor.fetchone()
        self.assertEquals(row,None)
        if settings.DATABASE_ENGINE == 'mysql':
            cursor.execute("show tables like 'schema_xml_basic%'")
            row = cursor.fetchone()
            self.assertEquals(row,None)
    
    def test3RemoveSchema(self):
        """ Test removing a more complicated schema """
        schema_model = create_xsd_and_populate("6_nestedrepeats.xsd", "6_nestedrepeats.xml")
        num_handled = SubmissionHandlingOccurrence.objects.all().count()
        self.assertEquals(1,num_handled)
        all_meta = Metadata.objects.all()
        count = all_meta.count()
        self.assertEquals(1,count)
        attachment = all_meta[0].attachment
        su = StorageUtility()
        su.remove_schema(schema_model.id)
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
            cursor.execute("show tables like 'schema_xml_nestedrepeats%'")
            row = cursor.fetchone()
            self.assertEquals(row,None)

    def test4DeleteInstance(self):
        """ Test instance data deletion from XFormmanager """
        formdefmodel_5 = create_xsd_and_populate("5_singlerepeat.xsd")
        instance_5 = populate("5_singlerepeat.xml")
        formdefmodel_6 = create_xsd_and_populate("6_nestedrepeats.xsd")
        instance_6 = populate("6_nestedrepeats.xml")
        xformmanager = XFormManager()

        num_handled = SubmissionHandlingOccurrence.objects.all().count()
        self.assertEquals(2,num_handled)
        count = Metadata.objects.all().count()
        self.assertEquals(2,count)
        
        # TODO - change this syntax once meta.attachment becomes meta.submission
        xformmanager.remove_data(formdefmodel_5.id, instance_5.xform.form_metadata.all()[0].raw_data )
        xformmanager.remove_data(formdefmodel_6.id, instance_6.xform.form_metadata.all()[0].raw_data )
        # Deleting xform instance does not actually delete submission yet - should it?
        #count = len(Submission.objects.all())
        #self.assertEquals(0,count)
        #count = len(Attachment.objects.all())
        #self.assertEquals(0,count)
        # test metadata deletion

        # Test that children have been marked as 'doubly handled' and remain 'initially handled'
        # (so that they are not considered 'orphans' i.e. unhandled)
        num_handled = SubmissionHandlingOccurrence.objects.all().count()
        self.assertEquals(4,num_handled)
        self.assertFalse(instance_5.is_orphaned())        
        self.assertFalse(instance_6.is_orphaned())        
        
        count = Metadata.objects.all().count()
        self.assertEquals(0,count)
        count = SubmissionHandlingOccurrence.objects.all().count()
        self.assertEquals(4,count)
        # test raw data deletion
        if settings.DATABASE_ENGINE == 'mysql':
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM schema_xml_singlerepeat")
            row = cursor.fetchall()
            self.assertEquals(len(row),0)
            cursor.execute("SELECT * FROM schema_xml_singlerepeat_root_userid")
            row = cursor.fetchone()
            self.assertEquals(row,None)
            cursor.execute("SELECT * FROM schema_xml_nestedrepeats")
            row = cursor.fetchone()
            self.assertEquals(row,None)
            cursor.execute("SELECT * FROM schema_xml_nestedrepeats_root_nested")
            row = cursor.fetchone()
            self.assertEquals(row,None)
        
    def test4DeleteSubmissionMetadata(self):
        """ This is more a sanity check than anything else. Makes sure
        Django deletes the entire dependency chain for Submission objects. """
        formdefmodel_5 = create_xsd_and_populate("5_singlerepeat.xsd")
        instance_5 = populate("5_singlerepeat.xml")
        formdefmodel_6 = create_xsd_and_populate("6_nestedrepeats.xsd")
        instance_6 = populate("6_nestedrepeats.xml")
        instance_5.delete()
        instance_6.delete()
        # receiver unit tests already check for count([Submission|Attachment]) = 0
        # so here we test for metadata deletion
        count = Metadata.objects.all().count()
        self.assertEquals(0,count)
        
    def tearDown(self):
        pass
        
