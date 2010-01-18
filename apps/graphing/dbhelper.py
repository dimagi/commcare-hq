from django.db import connection, transaction, DatabaseError
import logging
import os
import string
import time,datetime
import settings
from django.conf import *

string_type_codes = [253,252]
int_type_codes = [3]
date_type_codes = [12]
bool_type_codes = [1]

MMDDYYYY_FORMAT= '%m/%d/%Y'
XMLDATE_FORMAT= '%Y-%m-%dT%H:%M:%S'
OUTPUT_DATE_FORMAT = '%Y-%m-%d %H:%M'


def get_readable_date(sqldatestring):
    return ''

def get_dategroup_expr(date_colname, startdate, enddate):
        """Get the expression for a date you want to group by"""
        delta = enddate-startdate
                
        format_string = "'%%Y-%%m-%%d'"
#        if delta.days < 30:
#            format_string = "'%%Y-%%m-%%d'"            
#        elif delta.days > 30:
#            format_string = "'%%Y-%%m'"
#        elif delta.days > 360:
#            format_string = "'%%Y'"
            
        date_func = ''
        retclause = '%s(%s,%s)'
        
        if settings.DATABASE_ENGINE == 'mysql':
            #DATE_FORMAT(timecol,'%m') #or %%m to escape out the %
            date_func = "DATE_FORMAT"
            #date_colname
            #self.date_columns[self.default_date_column_id]
            retclause = retclause % (date_func,date_colname,format_string)
        elif settings.DATABASE_ENGINE == 'sqlite3':
            #strftime('%Y-%m-%d', timecol)
            date_func = "strftime"
            retclause = retclause % (date_func,format_string,date_colname)
            
        return retclause
        #return self.date_columns[0]    
    
def get_date_expr(date_colname,startdate, enddate):        
    """Get the date string expression you want for a select"""
        
    delta = enddate-startdate            
    format_string = "'%%m/%%d/%%Y'"        
    date_func = ''
    retclause = '%s(%s,%s)'
    
    if settings.DATABASE_ENGINE == 'mysql':
        #DATE_FORMAT(timecol,'%m') #or %%m to escape out the %
        date_func = "DATE_FORMAT"
        #self.date_columns[self.default_date_column_id]
        retclause = retclause % (date_func,date_colname,format_string)
    elif settings.DATABASE_ENGINE == 'sqlite3':
        #strftime('%Y-%m-%d', timecol)
        date_func = "strftime"
        #self.date_columns[self.default_date_column_id]
        retclause = retclause % (date_func,format_string,date_colname)
        
    return retclause
        

def get_date_whereclause(date_colname, startdate, enddate):
    """This is to change the date format function to use on the actual queries
       sqlite and mysql use different methodnames to do their date arithmetic"""    
    ret = " %s > '%s' AND %s < '%s' " % (date_colname,startdate.strftime('%Y-%m-%d'), 
                                         date_colname, enddate.strftime('%Y-%m-%d'))
    return ret



class DbHelper(object):    
    def __init__(self, tblname, dispname, default_date=None):        
        self.int_columns = []
        self.bool_columns = []
        self.str_columns = []       
        self.date_columns = []
        self.tablename = tblname
        self.displayname = dispname
        self.default_date_column_id = 0
        
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM " + self.tablename + " limit 1")        
        rows = cursor.fetchall()
        
        #parse the columns out:
        #type_code
        
        rawcolumns = cursor.description # in ((name,datatype,,,,),(name,datatype,,,,)...) THIS DOES NOT WORK IN SQLITE.  Must use MySQL
        for col in rawcolumns:
            name = col[0]
            code = col[1]
            
            if int_type_codes.count(code) == 1:
                self.int_columns.append(name)
            elif bool_type_codes.count(code) == 1:
                self.bool_columns.append(name)
            elif name.lower() == 'timestart' or name.lower() == 'timeend':
                #this is really ugly right now because xform dates are set into strings      
                self.date_columns.append(name)                
            elif string_type_codes.count(code) == 1:
                self.str_columns.append(name)        
            elif date_type_codes.count(code) == 1:
                self.date_columns.append(name)
    
        if len(self.date_columns) == 0:
            logging.warning("Warning, table " + self.tablename + " has no date column for time series.  Most functionality won't work.")
        else:
            if default_date != None:
                if self.date_columns.count(default_date) == 1:
                    self.default_date_column_id = self.date_columns.index(default_date)
    
    @property
    def default_date_column(self):
        return self.date_columns[self.default_date_column_id]
        
    
    def get_single_column_query_data(self, query):
        '''Get the results of an arbitrary sql query'''
        results = self.get_query_data(query)
        return [row[0] for row in results]
        
    def get_query_data(self,query):
        """Run the sql query and return the cursor"""
        cursor = connection.cursor()
        cursor.execute(query)
        return cursor.fetchall()        
    
    def get_uniques_for_column(self, columname):
        """Get an array of all the unique values in a given column.
           Results are returned sorted by the column."""
        col_to_use = columname        
        query = "select distinct(%s) from %s order by %s" % (columname, self.tablename, columname)
        return self.get_single_column_query_data(query)
    
    def get_uniques_for_columns(self, columns, delimiter='|'):
        """Get an array of all the unique values in a given set of columns,
           by concatenating them together separated by the delimeter.  
           Results are returned sorted by the concatenated string."""
        # this probably only works on mysql.  I think that's okay.
        concat_string = "concat_ws('%s', %s)" % (delimiter, ", ".join(columns))
        query = "select distinct %s as concatenated_result from %s order by concatenated_result" % (concat_string, self.tablename)
        return self.get_single_column_query_data(query)
    
    def get_uniques_for_column_date_bound(self, columname, startdate=None, enddate=None):
        """return an array of all the unique values in a given column, allowing 
           one to only include results between a pair of dates"""
        if len(self.date_columns) == 0:
            raise Exception("Unable to execute, table " + self.tablename + " has no usable datetime column")
        
        col_to_use = columname        
        
        query = "select distinct(" + col_to_use + ") from """ + self.tablename
        if startdate != None and enddate != None:
            query += " WHERE " + get_date_whereclause(col_to_use, startdate, enddate)
        return self.get_single_column_query_data(query)
                      
    
    def get_column_filter_hash(self, startdate, enddate):
        #todo:
        #for all string columns:
        #do a select distinct 
        #return hash for all those values
        ret = {}
        for col in self.str_columns:
            ret[col] = self.get_uniques_for_column(col, startdate, enddate)        
        return ret
    
    
    
    def get_filtered_date_count(self, startdate, enddate, filters = {}):
        """Special report query to give you for a given filtered count over a certain column value
        For example, if i know a username column, I want to get a daily count returns count, date
        
        Filters are a dictionary of {'colname','value} or {'colname':[value1,value2]}

        where colname=value
        or colname in (value1, value2)
        
        The lists ONLY WORK WITH LISTS OR TUPLES.  You can't pass in query sets.
        Also be careful with unicode strings, they don't work properly so call str() 
        on whatever you pass in the list.
        
        It will build a where clause  with the datetime values as criteria as well as the column filters.
        """
                      
        
        if len(self.date_columns) == 0:
            raise Exception("Unable to execute, table " + self.tablename + " has no usable datetime column")
        
        wherestring = " WHERE "
        for key, value in filters.items():
            
            valstring = ""            
            if isinstance(value,int):
                valstring = "%d" % (value)
            elif isinstance(value,list) or isinstance(value, tuple):
                # this sneakily parses to valid sql for ints and strings
                # use with care.
                valstring += str(tuple(value))                
            else:
                valstring = "'%s'" % (value)
            if isinstance(value,list) or isinstance(value,tuple):
                wherestring += "%s in %s AND " % (key,valstring)
            else:
                wherestring += " %s=%s AND " % (key, valstring)            
        try:
            query = "select count(*), " + get_date_expr(self.default_date_column, startdate,enddate) +\
                    " from " + self.tablename + wherestring +\
                    get_date_whereclause(self.default_date_column, startdate, enddate) +\
                    " group by " + get_dategroup_expr(self.default_date_column, startdate,enddate) +\
                    " order by " + self.default_date_column
            return self.get_query_data(query)
        except:
            return [] 
        
                
    
    #time.mktime(datetime.datetime.now().timetuple())
    def get_counts_dataset(self,startdate,enddate):
        if len(self.date_columns) == 0:
            raise Exception("Unable to execute, table " + self.tablename + " has no usable datetime column")
        
        if startdate == None:
            startdate = datetime.datetime.min
        if enddate == None:
            enddate = datetime.datetime.now()
        
        #select date_format(timestart,'%d'), count(*) from formname group by DATE_FORMAT(timestart,'%d') order by date_format(timestart,'%d');
        #query = "select timeend, count(*) from " + self.tablename + " group by DATE_FORMAT(timeend,'%%m') order by timeend"
        query = "select " + self.date_columns[0] + ", count(*) from " + self.tablename + " group by " + get_dategroup_expr(self.default_date_column, startdate,enddate) + " order by " + self.default_date_column
        #query = 'select timeend, id from ' + self.tablename
        #print query
        rows = self.get_query_data(query)
        ret = []        
        
        if len(rows ) == 0:
            ret.append([0,0])
        
        for row in rows:
            if isinstance(row[0],datetime.datetime):
                datelong = time.mktime(row[0].timetuple()) * 1000
                pass
            else:
                # czue - I don't know what this line is doing, all i know is that sometimes
                # row[0] is null, which makes this unhappy.
                if row[0] is not None:
                    datelong= time.mktime(time.strptime(str(row[0][0:-4]),XMLDATE_FORMAT))
                else: 
                    datelong="empty date"
            val = int(row[1])
            ret.append([datelong,val])
        dset = {}
        dset["label"] = self.displayname.__str__()
        dset["data"] = ret
        dset['bars'] = {'show' :'true' }
        return dset
    
    def get_integer_series_dataset(self):
        if len(self.date_columns) == 0:
            raise Exception("Unable to execute, table " + self.tablename + " has no usable datetime column")
        
        dset = {}
        for seriesname in self.int_columns:
           subset = {}
           query = 'select ' + self.default_date_column + ', ' + seriesname + ' from ' + self.tablename + ' order by ' + self.default_date_column + ' ASC'
           rows = self.get_query_data(query)
           vals = []
           if len(rows) == 0:
               vals.append([0,0])
               
           for row in rows:
               if isinstance(row[0],datetime.datetime):
                   datelong = time.mktime(row[0].timetuple()) * 1000           
               else:
                   datelong= time.mktime(time.strptime(str(row[0][0:-4]),XMLDATE_FORMAT))
               
               if row[1] != None:
                   val = int(row[1])
               else:
                   val = 0
               vals.append([datelong,val])
           subset['label'] = seriesname.__str__()
           subset['data'] = vals           
           dset[seriesname] = subset
        return dset
