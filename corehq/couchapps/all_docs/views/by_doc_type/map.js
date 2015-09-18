function (doc) {
    switch (doc.doc_type){
        case "CommCareCase":
        case "CommCareCase-Deleted":
        case "XFormInstance":
        case "XFormInstance-Deleted":
        case "XFormError":
        case "XFormError-Deleted":
        case "XFormDuplicate":
        case "XFormDuplicate-Deleted":
        case "XFormDeprecated":
        case "XFormDeprecated-Deleted":
        case "XFormArchived":
        case "XFormArchived-Deleted":
        case "SubmissionErrorLog":
        case "SubmissionErrorLog-Deleted":
        case "MessageLog":
        case "MessageLog-Deleted":
        case "CallLog":
        case "CallLog-Deleted":
        case "SMSLog":
        case "SMSLog-Deleted":
        case "EventLog":
        case "EventLog-Deleted":
            return;
    }

    emit(doc.doc_type, null);
}
