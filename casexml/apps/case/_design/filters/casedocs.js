/*
 * Filter that only returns cases.  Used by the change listener.
 */
function(doc, req)
{
    return (doc["doc_type"] == "CommCareCase");
}
