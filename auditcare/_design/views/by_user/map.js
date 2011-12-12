function(doc) {
    // these lines magically import our other javascript files.  DON'T REMOVE THEM!
    // !code util/shared_funcs.js

    if (doc.base_type == 'AuditEvent') {
        //user event classes
        emit(['user', doc.user, doc.doc_type], null);
    }
}