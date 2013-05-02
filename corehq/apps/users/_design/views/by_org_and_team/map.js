function (doc) {
    if (doc.doc_type == "WebUser" && doc.is_active) {
        var org_memberships = doc.org_memberships;
        for (var i = 0; i < org_memberships.length; i++) {
            var om = org_memberships[i];
            if (om.team_ids.length > 0) {
                for (var j = 0; j < om.team_ids.length; j++) {
                    emit([om.organization, om.team_ids[j]], null);
                }
            }
            else {
                emit([om.organization, "_"],  null);
            }
        }
    }
}
