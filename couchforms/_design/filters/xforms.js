/*
 * Filter that only returns xforms.  Used by the change listener.  
 */
function(doc, req)
{
    return (doc["doc_type"] == "XFormInstance" && doc['xmlns'] !== "http://code.javarosa.org/devicereport");
}
