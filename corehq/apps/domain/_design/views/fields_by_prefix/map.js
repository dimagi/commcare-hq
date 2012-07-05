function (doc) {
    if (doc.doc_type === "Domain") {
        ['project_type', 'phone_model', 'user_type', 'city', 'country', 'region'].forEach(function (field) {
            if (doc[field]) {
                emit([field, doc[field]], null);
            }
        });
    }
}