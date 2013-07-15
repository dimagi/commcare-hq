function(doc) {
    if(doc.base_doc === "MobileBackend" && doc.backend_type === "SMS" && !doc.is_global) {
        emit([doc.domain, doc.name], null);
        for(var i = 0; i < doc.authorized_domains.length; i++) {
            emit([doc.authorized_domains[i], doc.name], null);
        }
    }
}
