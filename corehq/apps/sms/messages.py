MSG_MULTIPLE_SESSIONS = "SURVEY_ERROR"
MSG_TOUCHFORMS_DOWN = "TOUCHFORMS_DOWN"
MSG_TOUCHFORMS_ERROR = "TOUCHFORMS_ERROR"
MSG_CHOICE_OUT_OF_RANGE = "SELECT_OUT_OF_RANGE"
MSG_INVALID_CHOICE = "SELECT_INVALID_CHOICE"
MSG_INVALID_INT = "INVALID_INT"
MSG_INVALID_FLOAT = "INVALID_FLOAT"
MSG_INVALID_LONG = "INVALID_LONG"
MSG_INVALID_DATE = "INVALID_DATE"
MSG_INVALID_TIME = "INVALID_TIME"
MSG_KEYWORD_NOT_FOUND = "KEYWORD_NOT_FOUND"
MSG_START_KEYWORD_USAGE = "START_KEYWORD_USAGE"
MSG_UNKNOWN_GLOBAL_KEYWORD = "UNKNOWN_GLOBAL_KEYWORD"
MSG_FIELD_REQUIRED = "FIELD_REQUIRED"
MSG_EXPECTED_NAMED_ARGS_SEPARATOR = "SS_NAMED_ARGS_SEPARATOR"
MSG_MULTIPLE_ANSWERS_FOUND = "SS_MULTIPLE_ANSWERS_FOUND"
MSG_MULTIPLE_QUESTIONS_MATCH = "SS_MULTIPLE_QUESTIONS_MATCH"
MSG_MISSING_EXTERNAL_ID = "MISSING_EXTERNAL_ID"
MSG_CASE_NOT_FOUND = "CASE_NOT_FOUND"
MSG_FIELD_DESCRIPTOR = "FIELD_DESCRIPTOR"

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
    MSG_KEYWORD_NOT_FOUND: "Keyword not found: '%(keyword)s'",
    MSG_START_KEYWORD_USAGE: "Usage: %(start_keyword)s <keyword>",
    MSG_UNKNOWN_GLOBAL_KEYWORD: "Unknown command: '%(keyword)s'",
    MSG_FIELD_REQUIRED: "This field is required.",
    MSG_EXPECTED_NAMED_ARGS_SEPARATOR: "Expected name and value to be joined by '%(separator)s'.",
    MSG_MULTIPLE_ANSWERS_FOUND: "More than one answer found for '%(arg_name)s'",
    MSG_MULTIPLE_QUESTIONS_MATCH: "More than one question matches '%(answer)s'",
    MSG_MISSING_EXTERNAL_ID: "Expected case external id.",
    MSG_CASE_NOT_FOUND: "Case with the given external id was not found.",
    MSG_FIELD_DESCRIPTOR: "Field '%(field_name)s': ",
}

def get_message(msg_id, verified_number=None, context=None):
    context = context or {}
    return _MESSAGES.get(msg_id, "") % context

