from django import template
from django.core.urlresolvers import reverse
from django.template import Library, Node


from graphing import dbhelper
register = template.Library()

import time

xmldate_format= '%Y-%m-%dT%H:%M:%S'
output_format = '%Y-%m-%d %H:%M'

class StringColumnsNode(Node):
    def __init__(self, content_object, context_name):
        self.table_name = template.Variable(content_object)
        self.var_name = context_name
    def render(self, context):
        
        nm = self.table_name.resolve(context)
        helper = dbhelper.DbHelper(nm, nm)        
        context[self.var_name] = helper.str_columns
        
        context[self.var_name].insert(0,'count(*)') 
        return ''

@register.tag_function
def get_string_columns(parser, token):
    error_string = "%r tag must be of format {%% get_string_columns for TABLE_NAME as CONTEXT_VARIABLE %%}" % token.contents.split()[0]
    try:
        split = token.split_contents()        
    except ValueError:
        raise template.TemplateSyntaxError(error_string)
    if len(split) == 5:
        return StringColumnsNode(split[2],split[4])
    else:
        raise template.TemplateSyntaxError(error_string)
    

class DatetimeColumnsNode(Node):
    def __init__(self, content_object, context_name):
        self.table_name = template.Variable(content_object)
        self.var_name = context_name
    def render(self, context):        
        nm = self.table_name.resolve(context)
        helper = dbhelper.DbHelper(nm, nm)        
        context[self.var_name] = helper.date_columns 
        return ''

@register.tag_function
def get_datetime_columns(parser, token):
    error_string = "%r tag must be of format {%% get_datetime_columns for TABLE_NAME as CONTEXT_VARIABLE %%}" % token.contents.split()[0]
    try:
        split = token.split_contents()        
    except ValueError:
        raise template.TemplateSyntaxError(error_string)
    if len(split) == 5:
        return DatetimeColumnsNode(split[2],split[4])
    else:
        raise template.TemplateSyntaxError(error_string)
    
class DataColumnsNode(Node):
    def __init__(self, content_object, context_name):
        self.table_name = template.Variable(content_object)
        self.var_name = context_name
    def render(self, context):        
        nm = self.table_name.resolve(context)
        helper = dbhelper.DbHelper(nm, nm)        
        context[self.var_name] = helper.int_columns + helper.bool_columns
        return ''

@register.tag_function
def get_data_columns(parser, token):
    error_string = "%r tag must be of format {%% get_data_columns for TABLE_NAME as CONTEXT_VARIABLE %%}" % token.contents.split()[0]
    try:
        split = token.split_contents()        
    except ValueError:
        raise template.TemplateSyntaxError(error_string)
    if len(split) == 5:
        return DataColumnsNode(split[2],split[4])
    else:
        raise template.TemplateSyntaxError(error_string)
    


class StringColumnValuesNode(Node):
    def __init__(self, colname, table_name, context_name):
        self.col_name = template.Variable(colname)
        self.table_name = template.Variable(table_name)
        self.var_name = context_name
    def render(self, context):        
        tbl = self.table_name.resolve(context)
        col = self.col_name.resolve(context)
        
        helper = dbhelper.DbHelper(tbl, tbl)        
        context[self.var_name] = helper.get_uniques_for_column(col)
        context[self.var_name].insert(0,'count(*)')
        return ''

@register.tag_function
def get_distinct_values_for_column(parser, token):
    error_string = "%r tag must be of format {%% get_distinct_values_for_column for <column> in <table> as CONTEXT_VARIABLE %%}" % token.contents.split()[0]
    try:
        split = token.split_contents()        
    except ValueError:
        raise template.TemplateSyntaxError(error_string)
    if len(split) == 7:
        return StringColumnValuesNode(split[2],split[4],split[6])
    else:
        raise template.TemplateSyntaxError(error_string)
    
    
    
    
    
@register.simple_tag
def build_next_url(table_name, str_column = None, str_column_value = None, datetime_column = None, data_column = None, display_mode = None):
    #reverse('view_content_item', kwargs= {}),ctype.id,edge[0].id,edge[0])
    baseurl = reverse('graphing.views.inspector',kwargs={'table_name':table_name}) + "?"
    if str_column:
        baseurl += "str_column=%s" % (str_column)    
    if str_column_value:
        baseurl += "&str_column_value=%s" % (str_column_value)
    if datetime_column:
        baseurl += "&datetime_column=%s" % (datetime_column)
    if data_column:
        baseurl += "&data_column=%s" % (data_column)
    if display_mode:
        baseurl += "&display_mode=%s" % (display_mode)    
    return baseurl