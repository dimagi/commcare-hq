"""
This file is currently just documentation as code,
but is formatted so as to be friendly to tooling we might write in order to
clean up these docs.
"""

from django.conf import settings

MAIN_DB = None
META_DB = None

# Doc types for classes we've removed from our code
# but may still have docs lying around from
DELETABLE_COUCH_DOC_TYPES = {
    'ApplicationAccess': (MAIN_DB,),
    'SurveyKeyword': (MAIN_DB,),
    'SurveyKeywordAction': (MAIN_DB,),
    'CaseReminder': (MAIN_DB,),
    'CaseReminderHandler': (MAIN_DB,),
    'CaseReminderEvent': (MAIN_DB,),
    'Dhis2Connection': (MAIN_DB,),
    'ExportMigrationMeta': (META_DB,),
    'ForwardingRule': (MAIN_DB,),
    'ForwardingRule-Deleted': (MAIN_DB,),
    'GlobalAppConfig': (settings.NEW_APPS_DB,),
    'WisePillDeviceEvent': (MAIN_DB,),
}
