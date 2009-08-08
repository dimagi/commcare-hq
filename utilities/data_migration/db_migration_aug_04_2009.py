# The following script performs a database-level migration from
# an old server (pre 8/1/2009) to a new server (post 8/1/2009).
#
# This script assumes it is running off an exact copy of the 
# OLD database, e.g. if a dumpscript was run and used to create
# this database exactly.
#
# Many projects were renamed resulting in the renaming of db
# tables that needs to be reflected here. 
#
# This script will also clear the entire contents of the 
# submission and xformmanager applications.  It is working
# under the assumption that the forms will be reimported
# manually through one of the other means (REST API), import/
# export scripts, etc.
#
# What will be left at the end of this are properly named tables
# filled with data, except for xformmanager and submission
# which will have no data.

from django.db import connection
from django.core.management.commands.syncdb import Command

def run():
    print "starting migration"
    from receiver.models import Submission, Attachment
    from xformmanager.models import FormDefModel, ElementDefModel, Metadata
    # this part of the script walks through all the registered
    # form definitions and deletes them.
    
    from xformmanager.storageutility import StorageUtility
    from graphing import dbhelper
    
    
    
    # let's do some sanity checks to make sure everything is working 
    # as planned.
    print "checking original database format"
    all_formdefs = FormDefModel.objects.all()
    all_tablenames = []
    all_elements = ElementDefModel.objects.all()
    print "found %s existing forms, %s elements" % (len(all_formdefs), len(all_elements))
    
    # first walk through all the expected tables and make sure they exist
    _check_data_tables(all_formdefs, all_tablenames)
    # this is temporarily commented out because the child tables are still acting
    # a bit funky.
    #_check_element_tables(all_elements)
    
    print "all tables exist pre-migration"
    
    # alright, let's clear them all now
    print "clearing xformmanager application"
    su = StorageUtility()
    su.clear(False)
        
    print "checking deletion of tables xformmanager tables"
    # now let's check make sure the forms and tables are gone
    form_count = len(FormDefModel.objects.all())
    if form_count != 0: 
        raise Exception("Not all forms were deleted!  %s remain." % (table, form))
    elem_count = len(ElementDefModel.objects.all())
    if elem_count != 0: 
        raise Exception("Not all elements were deleted!  %s remain." % (table, form))
    for tablename in all_tablenames:
        if _exists(tablename):
             raise Exception("Expected table %s to be deleted but it wasn't!" % (tablename))
    
    print "xformmanager cleanup verified"
    
    print "Migrating tables..."
    _perform_table_migration()
    print "Table migration verified"
    
    # now sync db.  we have to do this before submissions and attachments
    # are deleted because the new models expect foreign keys back to them 
    print "syncdb"
    _syncdb()
    print "done syncdb"
    
    all_submissions = Submission.objects.all()
    all_attachments = Attachment.objects.all()
    print "Cleaning up %s submissions and %s attachments" % (len(all_submissions), len(all_attachments))
    all_submissions.delete()
    all_attachments.delete()
    
    
    
    submission_count = len(Submission.objects.all())
    attachment_count = len(Attachment.objects.all())
    if submission_count != 0:
        raise Exception("Tried to delete all submissions but %s remained" % submission_count)
    if attachment_count != 0:
        raise Exception("Tried to delete all submissions but %s remained" % attachment_count)
    
    print "Submission cleanup verified"
    
    
def _check_data_tables(all_elements, all_tablenames):
    '''Makes sure the table for each element exists, and adds
       it to the passed in list of names.  This works on both
       formdef and elementdef objects, since they both support
       .tablename'''  
    for elem in all_elements:
        if not _exists(elem.table_name):
            raise Exception("Expected to find table %s for %s but did not!" % (elem.table_name, elem))
        all_tablenames.append(elem.table_name)

def _exists(table):
    cursor = connection.cursor()
    cursor.execute("show tables like '%s'" % table)
    return len(cursor.fetchall()) == 1

def _perform_table_migration():
    # moves any tables that have been renamed, but don't require
    # structural changes.
    
    table_remapping = {"organization_domain": "hq_domain",
                       "organization_extrole": "hq_extrole",
                       "organization_extuser": "hq_extuser",
                       "organization_organization": "hq_organization",
                       "organization_organization_members": "hq_organization_members",
                       "organization_organization_organization_type": "hq_organization_organization_type",
                       "organization_organization_supervisors": "hq_organization_supervisors",
                       "organization_organizationtype": "hq_organizationtype",
                       "organization_reporterprofile": "hq_reporterprofile",
                       "organization_reportschedule": "hq_reportschedule",
                       "dbanalyzer_basegraph": "graphing_basegraph",
                       "dbanalyzer_graphgroup": "graphing_graphgroup",
                       "dbanalyzer_graphgroup_graphs": "graphing_graphgroup_graphs",
                       "dbanalyzer_graphpref": "graphing_graphpref",
                       "dbanalyzer_graphpref_root_graphs": "graphing_graphpref_root_graphs",
                       "dbanalyzer_rawgraph": "graphing_rawgraph",
                       }
    for oldname, newname in table_remapping.items():
        _rename_table(oldname, newname)
    
    cursor = connection.cursor()
    # for some reason mysql insists on using these special slanted quote marks
    # for this command.  
    cursor.execute("ALTER TABLE `hq_domain` ADD COLUMN `timezone` VARCHAR(64) AFTER `description`;")
    cursor.execute("ALTER TABLE `receiver_submission` ADD COLUMN `content_type` VARCHAR(100) AFTER `bytes_received`;")
    
    # update null constraints
    cursor.execute("ALTER TABLE `xformmanager_metadata` MODIFY COLUMN `formname` VARCHAR(255) DEFAULT NULL;")
    cursor.execute("ALTER TABLE `xformmanager_metadata` MODIFY COLUMN `formversion` VARCHAR(255) DEFAULT NULL;")
    cursor.execute("ALTER TABLE `xformmanager_metadata` MODIFY COLUMN `deviceid` VARCHAR(255) DEFAULT NULL;")
    cursor.execute("ALTER TABLE `xformmanager_metadata` MODIFY COLUMN `username` VARCHAR(255) DEFAULT NULL;")
    cursor.execute("ALTER TABLE `xformmanager_metadata` MODIFY COLUMN `chw_id` VARCHAR(255) DEFAULT NULL;")
    cursor.execute("ALTER TABLE `xformmanager_metadata` MODIFY COLUMN `uid` VARCHAR(32) DEFAULT NULL;")

    
def _rename_table(oldname, newname):
    '''Renames a table, with some sanity checks'''  
    cursor = connection.cursor()
    if not _exists(oldname):
        raise Exception("Tried to rename %s but it didn't exist!" % oldname)
    if _exists(newname):
        raise Exception("Tried to rename %s to %s but the second already exists!" % (oldname, newname))
    cursor.execute("ALTER TABLE %s RENAME TO %s" % (oldname, newname))
    if not _exists(newname):
        raise Exception("Tried to rename %s to %s but it didn't work!" % (oldname, newname))
    if _exists(oldname):
        raise Exception("Tried to rename %s to %s but the old table was still there!" % (oldname, newname))
    
def _syncdb():
    sync = Command()
    sync.handle()
        