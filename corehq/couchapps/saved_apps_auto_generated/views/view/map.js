function(doc){
    if ((doc.doc_type == 'Application' || doc.doc_type == 'LinkedApplication') && doc.is_auto_generated) {
        emit([doc.domain, doc.copy_of], {
            doc_type: doc.doc_type,
            _id: doc._id,
            copy_of: doc.copy_of,
            domain: doc.domain,
            is_released: doc.is_released,
        });
    }
}
