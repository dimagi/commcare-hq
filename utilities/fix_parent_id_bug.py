'''
Created on Mar 26, 2010

@author: bderenzi
'''
import MySQLdb

HOST = "localhost"
USER = "root"
PASSWORD = ""
DB_NAME = "commcarehq_data"

def fix_table(table_name):
    q = "SELECT id, parent_id FROM " + table_name
    cursor.execute(q)
    
    result = cursor.fetchall()
    for r in result:
        # check that we don't update if parent_id = 1 because cory says those are correct
        # CZUE: unfortunately this isn't 100% true.  They are correct if the ID was supposed
        # to be 1, however 2 will actually go in as 1 as well.  I have no idea how to 
        # reconcile this cleanly
        if int(r[1]) == 1:
            continue
        
        q = "UPDATE " + table_name + " SET parent_id='" + str(r[1]+1) + "' WHERE id = " + str(r[0])
        cursor.execute(q)
        print q


def get_tables():
    q = '''
    SELECT xformmanager_elementdefmodel.table_name
    FROM xformmanager_elementdefmodel, xformmanager_formdefmodel
    WHERE xformmanager_elementdefmodel.form_id = xformmanager_formdefmodel.id
    	AND xformmanager_elementdefmodel.table_name <> xformmanager_formdefmodel.form_name
    '''

    cursor.execute(q)
    return cursor.fetchall()

    
'''
start here
'''
db = MySQLdb.connect(HOST,USER,PASSWORD,DB_NAME)
cursor = db.cursor()

for res in get_tables():
    table = res[0]
    print "Fixing: ", table
    try:
        fix_table(table)
    except Exception, e:
        print "Can't fix table '%s': %s", (table, e)
# 
# # normal brac domain
# # CZUE: need to fix this to work with all the other child tables on HQ as well
# fix_table("schema_brac_chp_homevisit_followup_brac_new_babies_8")
# fix_table("schema_brac_chp_homevisit_followup_brac_new_babies_10")
# fix_table("schema_brac_chp_homevisit_followup_brac_problem_death_10")
# fix_table("schema_brac_chp_homevisit_followup_brac_problem_death_6")
# fix_table("schema_brac_chp_homevisit_followup_brac_problem_death_8")
# fix_table("schema_brac_chp_homevisit_followup_brac_sick_person_10")
# fix_table("schema_brac_chp_homevisit_followup_brac_sick_person_8")
# 
# # dodoma domain
# fix_table("schema_dodoma_brac_chp_homevisit_followup_brac_new_babies_10")
# fix_table("schema_dodoma_brac_chp_homevisit_followup_brac_problem_death_10")
# fix_table("schema_dodoma_brac_chp_homevisit_followup_brac_sick_person_10")

# clean up
cursor.close ()
db.commit ()
db.close()
