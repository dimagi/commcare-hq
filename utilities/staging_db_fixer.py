# as result of wrong ini file settings, some 

import MySQLdb, MySQLdb.cursors
import os
import shutil

HOST = "localhost"
USER = "root"
PASSWORD = ""
DB_NAME = "commcarehq_staging"


db = MySQLdb.connect(HOST,USER,PASSWORD,DB_NAME) # , cursorclass=MySQLdb.cursors.DictCursor
cursor = db.cursor()

table_columns = (
    ('xformmanager_formdefmodel', 'xsd_file_location'),
    ('receiver_submission', 'raw_post'),
    ('receiver_attachment', 'filepath'),
    
)

for table, column in table_columns:

    q = "SELECT id, %s FROM %s WHERE %s LIKE '%%commcarehq_dev%%'" % (column, table, column)

    # print q 
    cursor.execute(q)
    result = cursor.fetchall()

    for r in result:
        print r
        cur_path = r[1]
        new_path = cur_path.replace('commcarehq_dev', 'commcarehq_staging')
        print "%s => %s" % (cur_path, new_path)
    
        shutil.move(cur_path, new_path)
    
        q = "UPDATE %s SET %s='%s' WHERE ID=%s" % (table, column, new_path, r[0])
        print q 
        cursor.execute(q)
