from django.db import models

from xformmanager.models import FormDefModel
from hq.models import Domain
import logging

class FormIdentifier(models.Model):
    '''An identifier for a form.  This is a way for a case to point at
       a particular form, using a particular column in that form.  It
       also allows you to pick an optional sorting column and sort order.  
       These are used to access the data in a particular order.'''
    
    form = models.ForeignKey(FormDefModel)
    # identity column can be either a single column, or a list of 
    # columns separated by pipes (|'s).  If it is a list the ids
    # will be concatenated lists of those columns, also separated
    # by pipes.  e.g. 123|56 (<chw_id>|<case_id>)
    identity_column = models.CharField(max_length=255, help_text=\
     """Identity column can be either a single column, or a list of 
        columns separated by pipes (|'s).  If it is a list the ids
        will be concatenated lists of those columns, also separated
        by pipes.  e.g. 123|56 (<chw_id>|<case_id>)""")
    
    # the column that defines how sorting works.  if no sorting is 
    # defined the case will assume each member of identity_column
    # appears exactly once, and this may behave unexpectedly if that
    # is not true
    sorting_column = models.CharField(max_length=255, null=True, blank=True)
    # sort ascending or descending
    sort_descending = models.BooleanField(default=True)
    
    
    def get_id_columns(self):
        '''Gets the list of columns out of this assuming that multiple.  
           Columns are separated by pipes.  If there is only one column
           this returns a single-item list containing that column'''
        return self.identity_column.split("|")
    
    def get_column_names(self):
        '''Gets the column names for this.  The only difference between
           calling this and the method on the form is that this will
           add a name equal to the identity column to the beginning
           of the list if the column is complex''' 
        form_cols = self.form.get_column_names()
        if self.has_complex_id():
           form_cols.insert(0, self.identity_column)
        return form_cols
            
    def get_rows(self):
        '''Gets all the rows for this.  The only difference between
           calling this and the method on the form is that this will
           add a value equal to concatenated identity column to the 
           beginning of each returned result if the column is complex.''' 
        # no complex id, just pass the query through to the form
        if self.sorting_column:
            data = self.form.get_rows(sort_column=self.sorting_column, 
                                      sort_descending=self.sort_descending)
        else:
            # no sorting column, just get everything in an arbitrary order.  
            data = self.form.get_rows()
        if self.has_complex_id():
            to_return = []
            sort_column_indices = self._get_form_column_indices()
            for row in data:
                updated_row = list(row)
                updated_row.insert(0,self._build_id(sort_column_indices, row))
                to_return.append(updated_row)
            return to_return
        return data
        
    def has_complex_id(self):
        '''Returns whether or not this is a complex id - pointing at
           multiple columns, or a simple one.'''
        return "|" in self.identity_column
    
    def _get_form_column_indices(self):
        '''Get the indices of the identity columns this references
           in the original form, as an ordered list of ints.'''
        # use the _form_'s columns, since we are returning the
        # indices of the columns according to the form.
        column_names = self.form.get_column_names()
        indices = []
        for id_column in self.get_id_columns():
            indices.append(column_names.index(id_column))
        return indices
    
    def _build_id(self, indices, row):
        # builds the case id from the row_dict, as it is in the database.
        # if the identity only points at a single column this will 
        # return just the value of that column.  Otherwise it will
        # concatenate the values of the columns specified separated
        # by pipes.
        values = []
        for index in indices:
            values.append(str(row[index]))
        return "|".join(values)
        
    
    def get_uniques(self):
        '''Return a list of unique values contained in this column'''
        return self.form.db_helper.get_uniques_for_columns(self.get_id_columns())
    
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
        data = self.get_rows()
        id_index = self.get_column_names().index(self.identity_column)
        to_return = {}
        for row in data:
            id_value = row[id_index]
            if not to_return.has_key(id_value):
                to_return[id_value] = []
            to_return[id_value].append(row)
        return to_return
    
    
    def get_data_for_case(self, case_id):
        '''Gets the list of entries for a single case.'''
        id_parts = case_id.split("|")
        id_cols = self.get_id_columns()
        if len(id_parts) != len(id_cols):
            # todo: what should happen here?  This is a fairly hard failure
            logging.error("In a case report, tried to get a %s-part id, but passed in a %s value" %
                          (len(id_cols), len(id_parts)))
            return []
        index_id_pairs = zip(id_cols, id_parts)
        filter_cols = [[col,"=", value] for col, value in index_id_pairs]
        if self.sorting_column:
            data = self.form.get_rows(column_filters=filter_cols,
                                      sort_column=self.sorting_column, 
                                      sort_descending=self.sort_descending)
        else:
            data = self.form.get_rows(column_filters=filter_cols)
        
        if self.has_complex_id():
            to_return = []
            # again, if we have a complex id, prepend it
            for row in data:
                row_as_list = list(row)
                row_as_list.insert(0, case_id)
                to_return.append(row_as_list)
            return to_return
        return data
    
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
        columns = self.get_column_names()
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
        '''Get the full list of column names, for all the forms.
           The first column is "case_id" and the rest are the forms'
           columns, in sequential order by form.'''
        to_return = [ "case_id" ]
        for form in self.form_data.order_by('sequence_id'):
            for col in form.form_identifier.get_column_names():
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

           { id_column_value_1: [case_id_1, form1_value1, form1_value2, ...,
                                 form2_value1, form2_value2, ...,
                                 ...],
             id_column_value_1: [case_id_2, form1_value1, form1_value2, ...,
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
            to_return[id] = [id] 
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
            # blarg.  some cases may have old forms that use integer
            # ids and new ones that use non ints.  in this case the
            # following can throw an exception, so just catch and 
            # swallow it here.
            try: 
                to_return[form_id] = form_id.get_data_for_case(case_id)
            except Exception, e:
                logging.warn("Couldn't get data from form %s for case %s.  Error is: %s" % (form_id, case_id, e))
                to_return[form_id] = []
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
       to the case.  This allows one to define what forms and columns
       make up a case, and use the sequence_id to define how the 
       data is ordered.'''
    form_identifier = models.ForeignKey(FormIdentifier)
    case = models.ForeignKey(Case, related_name="form_data")
    sequence_id = models.PositiveIntegerField()

    def __unicode__(self):
        return "%s %s: %s" % (self.case, self.sequence_id, self.form_identifier)
