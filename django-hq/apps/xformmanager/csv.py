from django.db import connection, transaction, DatabaseError
import settings
import logging
import os

SEPARATOR = ','

def generate_CSV(form_name):
    if form_name is None:
        logging.debug("Cannot generate CSV. No form name identified.")
        return
    logging.debug("Generating CSV for " + form_name)
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM " + form_name)
    rows = cursor.fetchall()
    
    if rows is None:
        logging.error("CVS: Form_name not recognized!")
        return
    f = open(  os.path.join(settings.CSV_PATH,form_name+".csv") , "w" )

    rawcolumns = cursor.description # in ((name,,,,,),(name,,,,,)...)
    for col in rawcolumns:
        f.write( col[0] + SEPARATOR )
    f.seek(-1,os.SEEK_CUR)
    f.write('\n')
    for row in rows:
        for field in row:
            f.write( str(field) + SEPARATOR )
        f.seek(-1,os.SEEK_CUR)
        f.write('\n')
    f.close()
    logging.debug("CSV generated successfully!")
    return
