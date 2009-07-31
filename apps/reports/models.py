from django.db import models

from xformmanager.models import FormDefModel
from hq.models import Domain

class FormIdentifier(models.Model):
    '''An identifier for a form.  This is a way for a case to point at
       a particular form, using a particular column in that form.  These
       also have sequence ids so that you can define the ordering of a
       full listing of the data for a case'''
    
    form = models.ForeignKey(FormDefModel)
    identity_column = models.CharField(max_length=255)
    # the column that defines how sorting works.  if no sorting is 
    # defined the case will assume each member of identity_column
    # appears exactly once, and this may behave unexpectedly if that
    # is not true
    sorting_column = models.CharField(max_length=255, null=True, blank=True)
    # sort ascending or descending
    sort_descending = models.BooleanField(default=True)
    
    
    def get_uniques(self):
        '''Return a list of unique values contained in this column'''
        return self.form.db_helper.get_uniques_for_column(self.identity_column)
    
    def get_data_lists(self):
        '''Gets all rows per unique identifier, sorted by the default
           sorting column.  What is returned is a dictionary of 
           lists of lists of the form:
           { id_column_value_1: [[value_1, value_2, value_3...],
                                 [value_1, value_2, value_3...],
                                 ...],
             id_column_value_2: [value_1, value_2, value_3...],
             ...
           }
           Each inner list represents a row of the data in 
           that form corresponding to the id column.  The lists
           will be ordered by the sorting column. 
           '''
        if self.sorting_column:
            list = self.form.get_rows(sort_column=self.sorting_column, 
                                      sort_descending=self.sort_descending)
            
        else:
            # no sorting column, just get everything in an arbitrary order.  
            list = self.form.get_rows()
        
        id_index = self.form.get_column_names().index(self.identity_column)
        to_return = {}
        for row in list:
            id_value = row[id_index]
            if not to_return.has_key(id_value):
                to_return[id_value] = []
            to_return[id_value].append(row)
        return to_return
    
    
    def get_data_for_case(self, case_id):
        '''Gets the list of entries for a single case.'''
        
        filter_col = [ [self.identity_column,'=',case_id] ]
        if self.sorting_column:
            return self.form.get_rows(column_filters=filter_col,
                                      sort_column=self.sorting_column, 
                                      sort_descending=self.sort_descending)
        else:
            return self.form.get_rows(column_filters=filter_col)
    
    
    def get_data_maps(self):
        '''Gets one row per unique identifier, sorted by the default
           sorting column.  What is returned is a dictionary of 
           lists of dictionaries of the form 
           { id_column_value_1: [{data_column_1: value_1,
                                  data_column_2: value_2,
                                  ...
                                 },
                                 {data_column_1: value_1,
                                  data_column_2: value_2,
                                  ...
                                 },
                                 ...
                                ]
             id_column_value_2: {data_column_1: value_1,
                                 data_column_2: value_2,
                                 ...
                                }
             ...
           }
           '''
        data_lists = self.get_data_lists()
        to_return = {}
        columns = self.form.get_column_names()
        for id, list in data_lists.items():
            # magically zip these up in a dictionary
            to_return[id] = [dict(zip(columns, sub_list)) for sub_list in list]
        return to_return
    
    
    def __unicode__(self):
        return "%s: %s" % (self.form, self.identity_column)

class Case(models.Model):
    '''A Case is a collection of data that represents a logically cohesive
       unit.  A case could be a case of a disease (e.g. Malaria) or could
       be an entire patient record.  In X-Form land, cases are collections
       of X-Form schemas that are linked together by a common identifier.'''
    
    name = models.CharField(max_length=255)
    domain = models.ForeignKey(Domain)
    
    def __unicode__(self):
        return self.name
    
    @property
    def forms(self):
        '''Get all the forms that make up this case'''
        forms = self.form_data.all()
        return [col.form_identifier.form for col in\
                self.form_data.all().order_by("sequence_id")]
    
    @property
    def form_identifiers(self):
        '''Get all the form identifiers that make up this case'''
        return [col.form_identifier for col in\
                self.form_data.all().order_by("sequence_id")]
    
    def get_unique_ids(self):
        '''Get the unique identifiers across the contained forms'''
        to_return = []
        for form_identifier in self.form_identifiers:
            for value in form_identifier.get_uniques():
                if value not in to_return:
                    to_return.append(value)
        return to_return        
        
    def get_column_names(self):
        '''Get the full list of column names, for all the forms'''
        to_return = []
        for form in self.form_data.order_by('sequence_id'):
            for col in form.form_identifier.form.get_column_names():
                # todo: what should these really be to differentiate
                # between the different forms?  the form name 
                # is probably too long, and the display name
                # can be null.  the id and sequence are both 
                # alright.  going with id for now.
                to_return.append("%s_%s" % (col, form.sequence_id))
        return to_return        
        
    def get_topmost_data(self):
        '''Get the full topmost (single most recent per form) 
           data set of data for all the forms.  This
           Will be a dictionary of the id column to a single flat
           row aggregating the data across the forms.  E.g.:

           { id_column_value_1: [form1_value1, form1_value2, ...,
                                 form2_value1, form2_value2, ...,
                                 ...],
             id_column_value_1: [form1_value1, form1_value2, ...,
                                 form2_value1, form2_value2, ...,
                                 ...],
             
             ...
           }
           
           The number of items in each list will be equal to the 
           sum of the number of columns of all forms that are a 
           part of this case.
           '''
        to_return = {}
        unique_ids = self.get_unique_ids()
        for id in unique_ids:
            to_return[id] = [] 
        for form_id in self.form_identifiers:
            data_list = form_id.get_data_lists()
            for id in unique_ids:
                if id in data_list:
                    to_return[id].extend(data_list[id][0])
                else:
                    # there was no data for this id for this
                    # form so extend the list with empty values
                    to_return[id].extend([None]*form_id.form.column_count)
        return to_return
    
    def get_topmost_data_maps(self):
        '''Get the full topmost (single most recent per form) 
           data set of data for all the forms in 
           dictionary format.  This ill be a dictionary of 
           dictionaries with the id column as keys and a 
           dictionary aggregating the data across the forms.  E.g.:
           { id_column_value_1: {form1_datacolumn1: form1_value1,
                                 form1_datacolumn2: form1_value2,
                                 ...,
                                 form2_datacolumn1: form2_value1,
                                 form2_datacolumn2: form2_value2,
                                },
             id_column_value_2: {form1_datacolumn1: form1_value1,
                                 form1_datacolumn2: form1_value2,
                                 ...
                                }
             ...
           }
           The number of items in each dict will be equal to the 
           sum of the number of columns of all forms that are a 
           part of this case.
        '''
        lists = self.get_topmost_data()
        to_return = {}
        columns = self.get_column_names()
        for id, list in lists.items():
            # magically zip these up in a dictionary
            to_return[id] = dict(zip(columns, list))
        return to_return
    
    def get_data_for_case(self, case_id):
        '''Gets all data for a single case.  The return format is a 
           dictionary form identifier objects to lists of rows for 
           that form.  If there is no data for the form, the value
           in the dictionary will be an empty list.  Example:
           { form_id_1 : [], # no data for this form
             form_id_2 : [[value1, value2, value3, ... ],
                          [value1, value2, value3, ... ],
                          ...
                         ],
             ...
            }
           '''
        to_return = {}
        for form_id in self.form_identifiers:
            to_return[form_id] = form_id.get_data_for_case(case_id) 
        return to_return
    
    
    def get_all_data(self):
        '''Get the full data set of data for all the forms.  This  
           Will be a dictionary of the id column to a dictionary 
           that has the same structure as what would be generated 
           by get_data_for_case on that id.  Example:
           { case_id_1 : { form_id_1 : [], # no data for this form
                           form_id_2 : [[value1, value2, value3, ... ],
                                        [value1, value2, value3, ... ],
                                        ...
                                       ],
                           ...
                          },
             case_id_2 : ...
             ... 
            }
           '''
        to_return = {}
        unique_ids = self.get_unique_ids()
        for id in unique_ids:
            to_return[id] = {}
        for form_id in self.form_identifiers:
            data_list = form_id.get_data_lists()
            for id in unique_ids:
                if id in data_list:
                    to_return[id][form_id] = data_list[id]
                else:
                    to_return[id][form_id] = []
        return to_return
    
    def get_all_data_maps(self):
        '''Get the full data set of data for all the forms in  
           dictionary format. This is analogous to the 
           get_all_data method, and the corresponding _maps 
           methods.  
        '''
        to_return = {}
        unique_ids = self.get_unique_ids()
        for id in unique_ids:
            to_return[id] = {}
        for form_id in self.form_identifiers:
            data_maps = form_id.get_data_maps()
            for id in unique_ids:
                if id in data_maps:
                    to_return[id][form_id] = data_maps[id]
                else:
                    to_return[id][form_id] = []
        return to_return
        
class CaseFormIdentifier(models.Model):
    # yuck.  todo: come up with a better name.
    '''A representation of a FormIdentifier as a part of a case.  This 
       contains a link to the FormIdentifier, a sequence id, and a link
       to the case.'''
    form_identifier = models.ForeignKey(FormIdentifier)
    case = models.ForeignKey(Case, related_name="form_data")
    sequence_id = models.PositiveIntegerField()

    def __unicode__(self):
        return "%s %s: %s" % (self.case, self.sequence_id, self.form_identifier)
