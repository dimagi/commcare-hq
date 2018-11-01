/*
 * Filter that returns documents that are neither cases nor forms.  Used by the change listener.
 */
function (doc, req) {
    var doc_type = doc["doc_type"];
    switch (doc_type) {
        case "XFormInstance":
        case "XFormArchived":
        case "XFormDeprecated":
        case "XFormDuplicate":
        case "XFormInstance-Deleted":
        case "HQSubmission":
        case "CommCareCase":
        case "CommCareCase-Deleted":
            return false;
        default:
            return true;
    }
}
