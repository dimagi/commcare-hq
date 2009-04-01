from django.db import connection, transaction, DatabaseError
import logging
import os
import string
import time,datetime

string_type_codes = [253,252]
int_type_codes = [3]
date_type_codes = [12]
bool_type_codes = [1]

xmldate_format= '%Y-%m-%dT%H:%M:%S.000'

output_format = '%Y-%m-%d %H:%M'




class DbHelper(object):    
    def __init__(self, tblname):        
        self.int_columns = []
        self.bool_columns = []
        self.str_columns = []       
        self.date_columns = []
        self.tablename = tblname
        
        
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
                self.date_columns.append(name)
            elif string_type_codes.count(code) == 1:
                self.str_columns.append(name)        
    def __doquery(self,query):
        cursor = connection.cursor()
        cursor.execute(query)
        return cursor.fetchall()        
            
    #time.mktime(datetime.datetime.now().timetuple())
    def get_counts_dataset(self,startdate,enddate):
        #select date_format(timestart,'%d'), count(*) from formname group by DATE_FORMAT(timestart,'%d') order by date_format(timestart,'%d');
        query = "select timeend, count(*) from " + self.tablename + " group by DATE_FORMAT(timeend,'%%m/%%d/%%Y') order by date_format(timeend,'%%m/%%d/%%Y')";
        #query = 'select timeend, id from ' + self.tablename
        #print query
        rows = self.__doquery(query)
        ret = []
        for row in rows:
            datelong= time.mktime(time.strptime(str(row[0]),xmldate_format))
            val = int(row[1])
            ret.append([datelong,val])
        
#        "russia": {
#            label: "Russia",
#            data: [[1988, 218000], [1989, 203000], [1990, 171000], [1992, 42500], [1993, 37600], [1994, 36600], [1995, 21700], [1996, 19200], [1997, 21300], [1998, 13600], [1999, 14000], [2000, 19100], [2001, 21300], [2002, 23600], [2003, 25100], [2004, 26100], [2005, 31100], [2006, 34700]]
#        },
        
        dset = {}
        dset["label"] = self.tablename.__str__()
        dset["data"] = ret
        return dset
    
    def get_integer_series_dataset(self):
        dset = {}
        for seriesname in self.int_columns:
           subset = {}
           query = 'select timeend, ' + seriesname + ' from ' + self.tablename + ' order by timeend ASC'
           rows = self.__doquery(query)
           vals = []
           for row in rows:
               datelong= time.mktime(time.strptime(str(row[0]),xmldate_format))
               if row[1] != None:
                   val = int(row[1])
               else:
                   val = 0
               vals.append([datelong,val])
           subset['label'] = seriesname.__str__()
           subset['data'] = vals           
           dset[seriesname] = subset
        return dset
           
    
    
    
    
    
            
        