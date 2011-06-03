function(doc) {
    
    if (doc.doc_type == "XFormInstance" )
    {
        emit(["d", doc.domain, doc.xmlns], 1);
        emit(["u", doc.domain, doc.form.meta.userID, doc.xmlns], 1);
    }
}