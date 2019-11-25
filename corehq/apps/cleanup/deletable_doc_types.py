"""
This file is currently just documentation as code,
but is formatted so as to be friendly to tooling we might write in order to
clean up these docs.
"""

MAIN_DB = None

# Doc types for classes we've removed from our code
# but may still have docs lying around from
DELETABLE_COUCH_DOC_TYPES = {
    'SurveyKeyword': (MAIN_DB,),
    'SurveyKeywordAction': (MAIN_DB,),
    'CaseReminder': (MAIN_DB,),
    'CaseReminderHandler': (MAIN_DB,),
    'CaseReminderEvent': (MAIN_DB,),
}
