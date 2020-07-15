function (doc) {
    if (doc.base_type == 'AuditEvent') {
        if (doc.doc_type == "NavigationEventAudit") {
            var generic_path = request_path;

            // Remove domain, using most permissive regex from those in corehq.apps.domain.utils
            generic_path = generic_path.replace(/^\/a\/[\w\.:-]+\//, '')

            // Remove any URL params
            generic_path = generic_path.replace(/\?.*/, '')

            emit([
                generic_path,
                doc.event_date,
                doc.request_path,
            ], null)
        }
    }
}
