function(doc) { 
    if (doc.doc_type == "PhoneCase") {
        emit(doc._id, doc);
    }
}