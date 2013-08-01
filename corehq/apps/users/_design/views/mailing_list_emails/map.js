function(doc) {
    if(doc.doc_type == "WebUser" &&
       doc.is_active &&
       doc.email &&
       !doc.email_opt_out) {
        emit(doc.email, null);
    }
}
