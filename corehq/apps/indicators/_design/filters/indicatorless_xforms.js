/*
 * Filter that only returns cases without indicators in the specified namespace.  Used by the change listener.
 */
function(doc, req)
{
    var namespaces = [];
    if (req.query.namespaces) {
        namespaces = req.query.namespaces.split(',');
    }

    var domains = [];
    if (req.query.domains) {
        domains = req.query.domains.split(',');
    }

    if (domains && namespaces) {
        for (var namespace in namespaces) {
            if (doc["doc_type"] === "XFormInstance"
                && !(doc.computed_  && namespace in doc.computed_)
                && domains.indexOf(doc.domain) >= 0) {
                return true;
            }
        }
    }
    return false;
}
