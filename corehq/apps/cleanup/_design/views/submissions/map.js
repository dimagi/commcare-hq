function(doc){
    if(doc.doc_type == "XFormInstance") {
        emit([
            doc.domain,
            doc.form.meta.userID,
            doc.form.meta.username,
            doc.form.meta.deviceID
        ],null);
    }
}