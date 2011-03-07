function(doc){
    if(doc.doc_type == "XFormInstance" && doc.repeats) {
        for (var i in doc.repeats) {
            var rep = doc.repeats[i];
            if (!rep.succeeded) {
                emit(rep.next_check, null);
            }
        }
    }
}