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

xmldate_format= '%Y-%m-%dT%H:%M:%S'
output_format = '%Y-%m-%d %H:%M'


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
        
        rawcolumns = cursor.description # in ((name,datatype,,,,),(name,datatype,,,,)...)
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
                    self.default_date_column_id = date_columns.index(default_date)
    
    def __doquery(self,query):
        """Run the sql query and return the cursor"""
        cursor = connection.cursor()
        cursor.execute(query)
        return cursor.fetchall()        
    
   
    def __get_dategroup_expr(self, startdate, enddate):
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
            retclause = retclause % (date_func,self.date_columns[self.default_date_column_id],format_string)
        elif settings.DATABASE_ENGINE == 'sqlite3':
            #strftime('%Y-%m-%d', timecol)
            date_func = "strftime"
            retclause = retclause % (date_func,format_string,self.date_columns[0])
            
        return retclause
        #return self.date_columns[0]    
    
    def __get_date_expr(self, startdate, enddate):        
        """Get the date string expression you want for a select"""
        
        if len(self.date_columns) == 0:
            raise Exception("Unable to execute, table " + self.tablename + " has no usable datetime column")
        
        
        delta = enddate-startdate
                
        format_string = "'%%m/%%d/%%Y'"
            
        date_func = ''
        retclause = '%s(%s,%s)'
        
        if settings.DATABASE_ENGINE == 'mysql':
            #DATE_FORMAT(timecol,'%m') #or %%m to escape out the %
            date_func = "DATE_FORMAT"
            retclause = retclause % (date_func,self.date_columns[self.default_date_column_id],format_string)
        elif settings.DATABASE_ENGINE == 'sqlite3':
            #strftime('%Y-%m-%d', timecol)
            date_func = "strftime"
            retclause = retclause % (date_func,format_string,self.date_columns[self.default_date_column_id])
            
        return retclause
            
    
    def __get_date_whereclause(self, startdate, enddate):
        """this is to change the date format function to use on the actual queries
        sqlite and mysql use different methodnames to do their date arithmetic"""        
        
        
        ret = " %s > '%s' AND %s < '%s' " % (self.date_columns[0],startdate.strftime('%Y-%m-%d'), self.date_columns[self.default_date_column_id], enddate.strftime('%Y-%m-%d'))
        return ret
        
    def get_uniques_for_column(self, columname, startdate=None, enddate=None):
        if len(self.date_columns) == 0:
            raise Exception("Unable to execute, table " + self.tablename + " has no usable datetime column")
        
        
        """return an array of all the unique values in a given column"""
        query = "select distinct(" + columname + ") from """ + self.tablename
        if startdate != None and enddate != None:
            query += " WHERE " + self.__get_date_whereclause(startdate, enddate)
        rows = self.__doquery(query)
        ret = []        
        
        if len(rows ) == 0:
            return ret
        for row in rows:
            ret.append(row[0])
        return ret              
    
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
        
        It will build a where clause  with the datetime values as criteria as well as the column filters.
        
        
        """
        
        if len(self.date_columns) == 0:
            raise Exception("Unable to execute, table " + self.tablename + " has no usable datetime column")
        
        wherestring = " WHERE "
        for key, value in filters.items():
            valstring = ""            
            if isinstance(value,int):
                valstring = "%d" % (value)
            elif isinstance(value,list):
                valstring += str(tuple(value))                
            else:
                valstring = "'%s'" % (value)
            
            if isinstance(value,list):
                wherestring += "%s in %s AND " % (key,valstring)
            else:
                wherestring += " %s=%s AND " % (key, valstring)            
        
        query = "select count(*), " + self.__get_date_expr(startdate,enddate) + " from " + self.tablename + wherestring + self.__get_date_whereclause(startdate, enddate) + " group by " + self.__get_dategroup_expr(startdate,enddate) + " order by " + self.date_columns[self.default_date_column_id]
        return self.__doquery(query)        
    
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
        query = "select " + self.date_columns[0] + ", count(*) from " + self.tablename + " group by " + self.__get_dategroup_expr(startdate,enddate) + " order by " + self.date_columns[self.default_date_column_id]
        #query = 'select timeend, id from ' + self.tablename
        #print query
        rows = self.__doquery(query)
        ret = []        
        
        if len(rows ) == 0:
            ret.append([0,0])
        
        for row in rows:
            datelong= time.mktime(time.strptime(str(row[0][0:-4]),xmldate_format))
            val = int(row[1])
            ret.append([datelong,val])
        
#        "russia": {
#            label: "Russia",
#            data: [[1988, 218000], [1989, 203000], [1990, 171000], [1992, 42500], [1993, 37600], [1994, 36600], [1995, 21700], [1996, 19200], [1997, 21300], [1998, 13600], [1999, 14000], [2000, 19100], [2001, 21300], [2002, 23600], [2003, 25100], [2004, 26100], [2005, 31100], [2006, 34700]]
#        },
        
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
           query = 'select ' + self.date_columns[self.default_date_column_id] + ', ' + seriesname + ' from ' + self.tablename + ' order by ' + self.date_columns[self.default_date_column_id] + ' ASC'
           rows = self.__doquery(query)
           vals = []
           if len(rows) == 0:
               vals.append([0,0])
               
           for row in rows:
               datelong= time.mktime(time.strptime(str(row[0][0:-4]),xmldate_format))
               if row[1] != None:
                   val = int(row[1])
               else:
                   val = 0
               vals.append([datelong,val])
           subset['label'] = seriesname.__str__()
           subset['data'] = vals           
           dset[seriesname] = subset
        return dset
           
    
    
    
    
    
            
        