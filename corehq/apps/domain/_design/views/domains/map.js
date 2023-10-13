function (doc) {
    /* Force rebuild -- can remove */
    if (doc.doc_type === "Domain") {
        emit(doc.name, null);
    }
}