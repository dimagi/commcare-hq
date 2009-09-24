# The following script performs a database-level migration from
# an old server (pre 9/23/2009) to a new server (post 9/23/2009).
#
# This script assumes it is running off an exact copy of the 
# OLD database, e.g. if a dumpscript was run and used to create
# this database exactly.
#
# This script does 4 main things
#
# 1. ALTER elementdefmodel.name to be elementdefmodel.xpath
# 2. version + uiversion in formdefmodel, metadata
# 3. change uniqueness constraints
# 4. update xpath values


""" OPTIONAL CONFIG """
SCHEMA_LOCATION = "C:\scratch\schemas"
CHANGE_SCHEMA_LOCATION = False

""" """""""""""""""""" """

from django.db import connection
from xformmanager.models import ElementDefModel, FormDefModel


from xformmanager.storageutility import get_registered_table_name
from django.db import connection

def run():
    print "starting update"
    _perform_table_migration()
    print "finished update"
    
def _perform_table_migration():
    cursor = connection.cursor()
    
    # 1. ALTER elementdefmodel.name to be elementdefmodel.xpath
    cursor.execute("ALTER TABLE `xformmanager_elementdefmodel` DROP KEY `name`;")
    cursor.execute("ALTER TABLE `xformmanager_elementdefmodel` CHANGE `name` `xpath` VARCHAR(255) NOT NULL;")

    # 2. version + uiversion in formdefmodel, metadata
    cursor.execute("ALTER TABLE `xformmanager_formdefmodel` ADD COLUMN `version` INT(11) DEFAULT NULL AFTER `target_namespace`;")
    cursor.execute("ALTER TABLE `xformmanager_formdefmodel` ADD COLUMN `uiversion` INT(11) DEFAULT NULL AFTER `version`;")
    cursor.execute("ALTER TABLE `xformmanager_metadata` ADD COLUMN `version` INT(11) DEFAULT NULL AFTER `formdefmodel_id`;")
    cursor.execute("ALTER TABLE `xformmanager_metadata` ADD COLUMN `uiversion` INT(11) DEFAULT NULL AFTER `version`;")
    
    # 3. change uniqueness constraints
    cursor.execute("ALTER TABLE `xformmanager_formdefmodel` DROP KEY `target_namespace`;")
    cursor.execute("ALTER TABLE `xformmanager_formdefmodel` ADD CONSTRAINT UNIQUE `target_namespace` (`target_namespace`,`version`);")
    cursor.execute("ALTER TABLE `xformmanager_elementdefmodel` ADD CONSTRAINT UNIQUE `xpath` (`xpath`,`form_id`);")

    # 4. update xpath values
    name_to_xpath_remapping = { # the following table was automatically generated in vi from a sqldump
                        "schema_mvp_safe_motherhood_registration_v0_3":"sampledata",
                        "schema_mvp_safe_motherhood_followup_v0_2":"safe_pregnancy",
                        "schema_mvp_safe_motherhood_followup_v0_1":"safe_pregnancy",
                        "schema_pathfinder_pathfinder_cc_follow_0_0_2":"pathfinder_followup",
                        "schema_mvp_safe_motherhood_referral_v0_2":"safe_pregnancy",
                        "schema_pathfinder_pathfinder_cc_registration_0_0_2":"pathfinder_registration",
                        "schema_brac_chw_chwvisit_v0_0_1":"brac",
                        "schema_pathfinder_pathfinder_cc_follow_0_0_2a":"pathfinder_followup",
                        "schema_pathfinder_pathfinder_cc_resolution_0_0_2a":"pathfinder_referral",
                        "schema_pathfinder_pathfinder_cc_resolution_0_0_2":"pathfinder_referral",
                        "schema_brac_chp_homevisit_v0_0_1":"brac",
                        "schema_pathfinder_pathfinder_cc_batch_registration_0_0_2":"pathfinder_registration",
                        "schema__batch_registration_0_0_2_pathfinder_registration_patient":"pathfinder_registration/patient",
                        "schema_intel_grameen_safe_motherhood_close_v0_2":"safe_pregnancy",
                        "schema_mvp_safe_motherhood_registration_v0_2":"sampledata",
                        "schema_pathfinder_pathfinder_cc_registration_0_0_2a":"pathfinder_registration",
                        "schema_intel_grameen_safe_motherhood_registration_v0_3":"sampledata",
                        "schema_mvp_safe_motherhood_referral_v0_1":"safe_pregnancy",
                        "schema_intel_grameen_safe_motherhood_followup_v0_2":"safe_pregnancy",
                        "schema_intel_grameen_safe_motherhood_referral_v0_2":"safe_pregnancy",
                        "schema_mvp_safe_motherhood_close_v0_2":"safe_pregnancy",
                        "schema_e_imci":"imci",
                        "schema_brac_brac_cc_resolution_0_0_2":"brac_referral",
                        "schema_survey2":"household",
                        "schema_brac_brac_chp_weekly":"brac_chp_weekly",
                        "schema_brac_safe_motherhood_registration_v0_3":"sampledata",
                        "schema_crs_ovc_registration_1":"crs_registration",
                        "schema_brac_safe_motherhood_followup_v0_2":"safe_pregnancy",
                        "schema_jyotsna1":"household",
                        "schema_brac_safe_motherhood_referral_v0_2":"safe_pregnancy",
                        "schema_brac_safe_motherhood_close_v0_2":"safe_pregnancy",
                        "schema_brac_brac_chw_weekly":"brac_chw_weekly",
                        "schema_crs_ovc_wellbeing_1":"crs_wellbeing",
                        "schema_crs_ovc_intervention_1":"crs_followup",
                        "schema_mvp":"household",
                        "schema_crs_ovc_termination_1":"crs_termination",
                       }
    count = 0
    for table_name, new_xpath in name_to_xpath_remapping.items():
        _rename_xpath(table_name, new_xpath)
        count = count + 1
    print "Updated %s elementdefmodel.xpath's" % count
    
    # the following is ONLY USEFUL for testing this script!
    # UNCOMMENT THIS WITH CAUTION
    # if CHANGE_SCHEMA_LOCATION: _change_schema_location()
    
    # we don't need to update any of the metadata elements
    # since all forms prior to this upgrade we assume are unversioned
    
def _rename_xpath(table_name, new_xpath):
    '''Updates xpath settings'''  
    # ensure that a valid ElementDefModel exists
    edm = ElementDefModel.objects.get(table_name=table_name)
    edm.xpath = new_xpath
    form = edm.form
    edm.save()
    # should return a unique instance of this elementdefmodel
    edm = ElementDefModel.objects.get(xpath=new_xpath, form=form)
    table_name = get_registered_table_name(edm.xpath, form.target_namespace)
    # test that table_name points to a valid table
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM %s" % table_name)
    # will throw a ProgrammingError if table does not exist
    print "Updated elementdefmodel %s" % edm.pk
    print "    %s exists" % table_name
    
def _change_schema_location():
    formdefs = FormDefModel.objects.all()
    count = 0
    for formdef in formdefs:
        if (formdef.xsd_file_location.find("/var/django-sites/commcarehq_dev/data/schemas") != -1):
            formdef.xsd_file_location = formdef.xsd_file_location.replace("/var/django-sites/commcarehq_dev/data/schemas",SCHEMA_LOCATION)
            formdef.save()
            count = count + 1
    print "changed schema locations for %s formdefmodels" % count
