function (doc) {
    if (doc.doc_type === "Domain") {
        ['project_type', 'phone_model', 'user_type', 'city', 'country', 'region', 'author', 'license'].forEach(function (field) {
            if (doc[field]) {
                emit([field, doc.is_snapshot && doc.is_approved && doc.published, doc[field]], null);
            }
        });
    }
}