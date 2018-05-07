function(doc) {
    if(doc.doc_type == "WebUser" &&
       doc.is_active &&
       doc.email &&
       !doc.email_opt_out &&
       doc.domains.length !== 0) {
        emit(doc.email, null);
    }
}
