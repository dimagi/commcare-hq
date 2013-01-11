/*
 * Filter that only returns cases without indicators in the specified namespace.  Used by the change listener.
 */
function(doc, req) {
    if (doc["doc_type"] === "XFormInstance") {
        var namespaces = [];
        if (req.query.namespaces) {
            namespaces = req.query.namespaces.split(',');
        }

        var computed_namespaces = [];
        if (doc.computed_) {
            computed_namespaces = Object.keys(doc.computed_);
        }

        var domains = [];
        if (req.query.domains) {
            domains = req.query.domains.split(',');
        }

        if (domains && namespaces) {
            for (var n in namespaces) {
                var namespace = namespaces[n];
                if (computed_namespaces.indexOf(namespace) < 0
                    && domains.indexOf(doc.domain) >= 0) {
                    return true;
                }
            }
        }
    }
    return false;
}
