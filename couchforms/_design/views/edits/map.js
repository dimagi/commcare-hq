function (doc) {
    //function to reveal prior edits of xforms.
    if(doc['doc_type'] == "XFormDeprecated") {
        emit(doc.orig_id, null);
    }
}
