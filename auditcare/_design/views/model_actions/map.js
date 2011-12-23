function(doc) {
    //basic emission of itemized audit events
    if (doc.base_type == 'AuditEvent') {
        if (doc.doc_type == "ModelActionAudit") {
            var val_dict = {};
            val_dict['rev'] = doc.revision_id;
            val_dict['event_date'] = doc.event_date;
            val_dict['checksum'] = doc.revision_checksum;
            emit(['model_types', doc.object_type, doc.object_uuid], val_dict);
        }
    }
}