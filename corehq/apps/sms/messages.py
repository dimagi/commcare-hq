MSG_MULTIPLE_SESSIONS = "sms.survey.restart"
MSG_TOUCHFORMS_DOWN = "sms.survey.temporarilydown"
MSG_TOUCHFORMS_ERROR = "sms.survey.internalerror"
MSG_CHOICE_OUT_OF_RANGE = "sms.validation.outofrange"
MSG_INVALID_CHOICE = "sms.validation.invalidchoice"
MSG_INVALID_INT = "sms.validation.invalidint"
MSG_INVALID_FLOAT = "sms.validation.invalidfloat"
MSG_INVALID_LONG = "sms.validation.invalidlong"
MSG_INVALID_DATE = "sms.validation.invaliddate"
MSG_INVALID_TIME = "sms.validation.invalidtime"
MSG_KEYWORD_NOT_FOUND = "sms.keyword.notfound"
MSG_START_KEYWORD_USAGE = "sms.keyword.startusage"
MSG_UNKNOWN_GLOBAL_KEYWORD = "sms.keyword.unknownglobal"
MSG_FIELD_REQUIRED = "sms.survey.fieldrequired"
MSG_EXPECTED_NAMED_ARGS_SEPARATOR = "sms.structured.missingseparator"
MSG_MULTIPLE_ANSWERS_FOUND = "sms.structured.multipleanswers"
MSG_MULTIPLE_QUESTIONS_MATCH = "sms.structured.ambiguousanswer"
MSG_MISSING_EXTERNAL_ID = "sms.caselookup.missingexternalid"
MSG_CASE_NOT_FOUND = "sms.caselookup.casenotfound"
MSG_FIELD_DESCRIPTOR = "sms.survey.fielddescriptor"

_MESSAGES = {
    MSG_MULTIPLE_SESSIONS: "An error has occurred. Please try restarting the survey.",
    MSG_TOUCHFORMS_DOWN: "An error has occurred. Please try again later. If the problem persists, try restarting the survey.",
    MSG_TOUCHFORMS_ERROR: "Internal server error.",
    MSG_CHOICE_OUT_OF_RANGE: "Choice is out of range.",
    MSG_INVALID_CHOICE: "Invalid choice.",
    MSG_INVALID_INT: "Invalid integer entered.",
    MSG_INVALID_FLOAT: "Invalid floating point number entered.",
    MSG_INVALID_LONG: "Invalid long integer entered.",
    MSG_INVALID_DATE: "Invalid date format: expected YYYYMMDD.",
    MSG_INVALID_TIME: "Invalid time format: expected HHMM (24-hour).",
    MSG_KEYWORD_NOT_FOUND: "Keyword not found: '{0}'",
    MSG_START_KEYWORD_USAGE: "Usage: {0} <keyword>",
    MSG_UNKNOWN_GLOBAL_KEYWORD: "Unknown command: '{0}'",
    MSG_FIELD_REQUIRED: "This field is required.",
    MSG_EXPECTED_NAMED_ARGS_SEPARATOR: "Expected name and value to be joined by '{0}'.",
    MSG_MULTIPLE_ANSWERS_FOUND: "More than one answer found for '{0}'",
    MSG_MULTIPLE_QUESTIONS_MATCH: "More than one question matches '{0}'",
    MSG_MISSING_EXTERNAL_ID: "Expected case external id.",
    MSG_CASE_NOT_FOUND: "Case with the given external id was not found.",
    MSG_FIELD_DESCRIPTOR: "Field '{0}': ",
}

def get_message(msg_id, verified_number=None, context=None):
    msg = _MESSAGES.get(msg_id, "")
    if context:
        msg = msg.format(context)
    return msg

