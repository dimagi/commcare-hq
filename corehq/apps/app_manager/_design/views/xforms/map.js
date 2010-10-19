function(doc) {
    if(doc['doc_type'] == 'XForm' && doc['xmlns']) {
        emit(doc['xmlns'], doc);
    }
}