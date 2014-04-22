function(doc) {
  if (doc.doc_type == "WebUser" && doc.is_active) {
     var domain_memberships = doc.domain_memberships;
        for (var i = 0; i < domain_memberships.length; i++) {
            var dm = domain_memberships[i];
            if(dm.role_id) {
                emit([dm.domain, dm.role_id], null)
            }
        }
  }
}