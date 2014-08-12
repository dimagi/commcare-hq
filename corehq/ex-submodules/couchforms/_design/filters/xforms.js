/*
 * Filter that only returns xforms.  Used by the change listener.  
 */
function(doc, req)
{
	if (doc['xmlns'] == "http://code.javarosa.org/devicereport") {
		return false;
	}
    var doc_type = doc["doc_type"];

    switch (doc_type) {
        case "XFormInstance":
        case "XFormArchived":
        case "XFormDeprecated":
        case "XFormDuplicate":
        case "XFormInstance-Deleted":
        case "HQSubmission":
            return true;
        default:
            return false;
    }
}
