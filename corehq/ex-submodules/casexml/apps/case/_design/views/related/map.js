function(doc) {
    if(doc.doc_type == "CommCareCase") {
        if (doc.indices) {
            for (var i = 0; i < doc.indices.length; i++) {
                emit([doc.domain, doc._id, "index"], doc.indices[i]);

                var reverse_index = {};
                for (var key in doc.indices[i]){
                    reverse_index[key] = doc.indices[i][key];
                }
                reverse_index.referenced_id = doc._id;

                emit([doc.domain, doc.indices[i].referenced_id, "reverse_index", doc.indices[i].relationship],
                     reverse_index);
            }
        }
    }
}
