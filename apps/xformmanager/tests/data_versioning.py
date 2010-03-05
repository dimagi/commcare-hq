import unittest
from decimal import Decimal
from datetime import *

from django.db import connection

from hq.dbutil import get_column_names
from xformmanager.tests.util import *
from xformmanager.xformdef import FormDef
from xformmanager.models import FormDataGroup, FormDataColumn

class DataVersioningTestCase(unittest.TestCase):
    """This class tests the creating of the form data management objects
       from different collections of forms."""

    def setUp(self):
        clear_data()
        self.original_formdef = create_xsd_and_populate("data/versioning/base.xsd")
        
    def tearDown(self):
        clear_data()
        clear_group_data()
        
    
    def testFromSingle(self):
        """Tests the creation of a form group from a single form."""
        self.assertEqual(0, FormDataColumn.objects.count())
        dom = Domain.objects.all()[0]
        group = FormDataGroup.from_forms([self.original_formdef], dom)
        self.assertEqual(group.columns.count(), FormDataColumn.objects.count())
        self.assertEqual(1, len(group.forms.all()))
        self.assertEqual(self.original_formdef, group.forms.all()[0])
        self.assertEqual(dom, group.domain)
        columns = self.original_formdef.get_data_column_names()
        self.assertEqual(len(columns), len(group.columns.all()))
        for column in columns:
            # Make sure this returns exactly one.  By calling "get"
            # more or less than 1 will raise an exception
            column_def = group.columns.get(name=column)
            self.assertEqual(1, len(column_def.fields.all()))
            field = column_def.fields.all()[0]
            self.assertEqual(self.original_formdef, field.form)
            self.assertEqual(column, field.column_name)
    
        # now remove the form.  This should be the equivalent of
        # removing every single column
        group.remove_form(self.original_formdef)
        group = FormDataGroup.objects.get(id=group.id)
        self.assertEqual(0, group.columns.count())
        self.assertEqual(0, FormDataColumn.objects.count())
        
    def testFromIdentical(self):
        """Tests the creation of a form group from two identical forms
           (with different version numbers)."""
        duplicate_formdef = create_xsd_and_populate("data/versioning/base.2.xsd")
        forms = [self.original_formdef, duplicate_formdef]
        dom = Domain.objects.all()[0]
        group = FormDataGroup.from_forms(forms, dom)
        self.assertEqual(2, len(group.forms.all()))
        for form in group.forms.all():
            self.assertTrue(form in forms)
        
        columns = self.original_formdef.get_data_column_names()
        self.assertEqual(len(columns), len(group.columns.all()))
        for column in columns:
            column_def = group.columns.get(name=column)
            self.assertEqual(2, len(column_def.fields.all()))
            for field in column_def.fields.all():
                self.assertTrue(field.form in forms)
                self.assertEqual(column, field.column_name)
    
    def testFull(self):
        """Tests the creation of a form group from several forms,
           including added, deleted, and changed fields."""
        fd2_dup = create_xsd_and_populate("data/versioning/base.2.xsd")
        fd3_add = create_xsd_and_populate("data/versioning/base.3.addition.xsd")
        fd4_del = create_xsd_and_populate("data/versioning/base.4.deletion.xsd")
        fd5_mod = create_xsd_and_populate("data/versioning/base.5.data_type_change.xsd")
        
        original_list = [self.original_formdef, fd2_dup, fd3_add, fd4_del, fd5_mod] 
                                          
        dom = Domain.objects.all()[0]
        group = FormDataGroup.from_forms(original_list, dom)
        self.assertEqual(5, len(group.forms.all()))
        for form in group.forms.all():
            self.assertTrue(form in original_list)
        
        columns = self.original_formdef.get_data_column_names()
        # this is added by form 3
        columns.append("root_added_field")
        # a second one of these is added by form 5
        columns.append("meta_username_2")
        self.assertEqual(len(columns), len(group.columns.all()))

        for group_column in group.columns.all():
            self.assertTrue(group_column.name in columns, 
                            "%s was found in the list of columns: %s" % \
                            (group_column.name, columns))
        
        for form in original_list:
            self._check_columns(form, group)
            
        # also make sure the view was created.
        query = "SELECT * from %s" % group.view_name
        cursor = connection.cursor()
        cursor.execute(query)
        view_cols_expected = ["form_id"]
        view_cols_expected.extend(columns)
        view_column_names = get_column_names(cursor)
        for view_column in view_column_names:   
            self.assertTrue(view_column in view_cols_expected,
                            "%s was found in the list of view columns" % \
                            view_column)
            
        # test deletion.  
        orig_col_count = group.columns.count()
        group.remove_form(fd3_add)
        group = FormDataGroup.objects.get(id=group.id)
        self.assertEqual(group.columns.count(), orig_col_count - 1)
        self.assertFalse("root_added_field" in group.columns.values_list("name", flat=True))
        
        # test adding it back
        group.add_form(fd3_add)
        group = FormDataGroup.objects.get(id=group.id)
        self.assertEqual(group.columns.count(), orig_col_count)
        columns.append("root_added_field")
        self.assertTrue("root_added_field" in group.columns.values_list("name", flat=True))
        
            
    def testDeleteClearsView(self):
        dom = Domain.objects.all()[0]
        group = FormDataGroup.from_forms([self.original_formdef], dom)
        query = "SELECT * from %s" % group.view_name
        group.delete()
        try:
            query = "SELECT * from %s" % group.view_name
            self.fail("Selecting from the view did not trigger an error after the form was deleted!")
        except Exception, e:
            pass
        
    def testFormsSharePointers(self):
        # make two groups from the same forms.  These should share columns
        dom = Domain.objects.all()[0]
        group = FormDataGroup.from_forms([self.original_formdef], dom)
        num_cols = group.columns.count()
        self.assertEqual(num_cols, FormDataPointer.objects.count())
        group2 = FormDataGroup.from_forms([self.original_formdef], dom) 
        self.assertEqual(num_cols, FormDataPointer.objects.count())
        
        
    def testDeleteClearsColumns(self):
        dom = Domain.objects.all()[0]
        group = FormDataGroup.from_forms([self.original_formdef], dom)
        num_cols = group.columns.count()
        self.assertEqual(num_cols, FormDataColumn.objects.count())
        
        # this should clear the columns
        group.delete()
        self.assertEqual(0, FormDataColumn.objects.count())
        self.assertEqual(0, FormDataPointer.objects.count())
        
        
    def _check_columns(self, form, group):
        columns = form.get_data_column_names()
        column_types = form.get_data_column_types()
        column_map = dict(zip(columns, column_types))
        group_columns = group.columns.filter(fields__form=form)
        self.assertEqual(len(columns), len(group_columns))
        for column in group_columns:
            # this is a hacky way of allowing the test that duplicates a field
            # (which intentionally appends a _2 to the column name) to call this 
            # shared method.
            if column.name in column_map:
                # this is correct
                found_name = column.name 
            elif (column.name.replace("_2", "") in column_map):
                # this is the duplicate column, also good
                found_name = column.name.replace("_2", "") 
            else:
                self.fail("No match for %s found in %s columns!" %\
                          (column.name, form))
            self.assertEqual(column.data_type, column_map[found_name])
            
            