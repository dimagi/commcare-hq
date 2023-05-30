"""
This file is currently just documentation as code,
but is formatted so as to be friendly to tooling we might write in order to
clean up these docs.
"""

from django.conf import settings

MAIN_DB = None
FIXTURES_DB = 'fixtures'

# Doc types for classes we've removed from our code
# but may still have docs lying around from
DELETABLE_COUCH_DOC_TYPES = {
    'ApiUser': (MAIN_DB,),
    'ApplicationAccess': (MAIN_DB,),
    'AuditCommand': ('auditcare',),
    'CaseReminder': (MAIN_DB,),
    'CaseReminderHandler': (MAIN_DB,),
    'CaseReminderEvent': (MAIN_DB,),
    'CommtrackConfig': (MAIN_DB,),
    'CustomDataFieldsDefinition': (settings.META_DB,),
    'DefaultConsumption': (MAIN_DB,),
    'Dhis2Connection': (MAIN_DB,),
    'ExportMigrationMeta': (settings.META_DB,),
    'ForwardingRule': (MAIN_DB,),
    'ForwardingRule-Deleted': (MAIN_DB,),
    'GlobalAppConfig': (settings.APPS_DB,),
    'HqDeploy': (MAIN_DB,),
    'ILSGatewayConfig': (MAIN_DB,),
    'Invitation': (settings.USERS_GROUPS_DB,),
    'ModelActionAudit': ('auditcare',),
    'RegistrationRequest': (MAIN_DB,),
    'StandaloneTranslationDoc': (MAIN_DB,),
    'SurveyKeyword': (MAIN_DB,),
    'SurveyKeywordAction': (MAIN_DB,),
    'WisePillDeviceEvent': (MAIN_DB,),
    '*': ('commcarehq__m4change',),
    'PactPatientCase': (MAIN_DB,),  # subclass of CommCareCase
    'CDotWeeklySchedule': (MAIN_DB,),
    'CObservation': (MAIN_DB,),
    'CObservationAddendum': (MAIN_DB,),
    'FixtureDataType': (FIXTURES_DB,),
    'FixtureDataItem': (FIXTURES_DB,),
    'FixtureOwnership': (FIXTURES_DB,),
}
