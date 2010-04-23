from django.db import connection, transaction, DatabaseError
import settings
import logging
import os

SEPARATOR = ','

def get_datacursor(form_name, argument_hash):
    """Return tuple of (columns, data) from the raw sql tables"""
    if form_name is None:
        logging.debug("Cannot generate CSV. No form name identified.")
        return
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM " + form_name)
    rows = cursor.fetchall()
    
    if rows is None:
        logging.error("CSV: Form_name not recognized!")
        return
    
    rawcolumns = cursor.description # in ((name,,,,,),(name,,,,,)...)
    columnarr = []
    for col in rawcolumns:
        columnarr.append(col[0])
    
    return (rows, columnarr)    

def raw_query(query):   
    cursor = connection.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    
    if rows is None:
        logging.error("CSV: Form_name not recognized!")
        return
    
    rawcolumns = cursor.description # in ((name,,,,,),(name,,,,,)...)
    columnarr = []
    for col in rawcolumns:
        columnarr.append(col[0])
    
    return (rows, columnarr)
    

def get_scalar(query):    
    cursor = connection.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    
    if rows is None:
        logging.error("CSV: get_scalar had an error!")
        return None
        
    for row in rows:
        for field in row:
            return field
    return None
        
    