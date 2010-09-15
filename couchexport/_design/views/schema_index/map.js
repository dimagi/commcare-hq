function (doc) {
    if (doc["#export_tag"]) {
        emit(doc[doc["#export_tag"]], doc);
    }
    else if (doc['doc_type']) {
        emit(doc['doc_type'], doc);
    }
}