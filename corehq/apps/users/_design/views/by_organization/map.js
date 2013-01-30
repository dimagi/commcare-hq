function (doc) {
    if (doc.doc_type == "WebUser" && doc.is_active) {
        var org_memberships = doc.org_memberships;
        for (var i = 0; i < org_memberships.length; i++) {
            emit(org_memberships[i].organization,  null);
        }
    }
}