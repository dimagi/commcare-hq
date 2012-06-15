function(doc) {
    if(doc.doc_type == "CommCareCase") {
        if (doc.indices) {
            for (var i = 0; i < doc.indices.length; i++) {
                emit([doc.domain, doc._id, "index"], doc.indices[i]);
                
                var reverse_index = {
                    identifier:      doc.indices[i].identifier,
                    referenced_type: doc.indices[i].referenced_type,
                    referenced_id:   doc._id
                };
                emit([doc.domain, doc.indices[i].referenced_id, "reverse_index"], reverse_index);
            }
        }
    }
}