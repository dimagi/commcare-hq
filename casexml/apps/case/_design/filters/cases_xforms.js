/*
 * Filter that only returns xforms OR cases.  Used by the change listener.
 */
function(doc, req)
{
    return (doc["doc_type"] == "CommCareCase" || doc["doc_type"] == "XFormInstance");
}
