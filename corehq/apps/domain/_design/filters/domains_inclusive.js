/*
 * Filter that returns all types of domains.  Used by the change listener.
 */
function(doc, req)
{
    var doc_type = doc["doc_type"];

    switch (doc_type) {
        case "Domain":
        case "Domain-DUPLICATE":
            return true;
        default:
            return false;
    }
}
