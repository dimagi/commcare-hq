function(doc) {
    // !code util/reports_forms.js
    if(doc.doc_type == "XFormInstance" && get_user_id(doc) != null) {
        // Note: if the user_id is null, that likely means it is a device log, so not a form we care about here.
        emit([doc.domain, get_user_id(doc)], {
            username: get_username(doc),
        });
    }
}
