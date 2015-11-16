function(doc) {
    if(doc.doc_type == "CommCareCase") {
        if (doc.indices) {
            for (var i = 0; i < doc.indices.length; i++) {
                var index = {};
                for (var key in doc.indices[i]){
                    if (doc.indices[i].hasOwnProperty(key)){
                        index[key] = doc.indices[i][key];
                    }
                }
                index.relationship = index.relationship || "child";
                emit([doc.domain, doc._id, "index"], index);

                var reverse_index = {};
                for (var key in doc.indices[i]){
                    if (doc.indices[i].hasOwnProperty(key)){
                        reverse_index[key] = doc.indices[i][key];
                    }
                }
                reverse_index.referenced_id = doc._id;
                reverse_index.relationship = reverse_index.relationship || "child";

                // Emit "child" relationship if there is no relationship set
                var relationship = doc.indices[i].relationship || "child";
                emit([doc.domain, doc.indices[i].referenced_id, "reverse_index", relationship],
                     reverse_index);
            }
        }
    }
}
