// Lighter weight view doc that strips out actions and xform ids
// which can get really unwieldy.
function (doc) {
    if (doc.doc_type === 'CommCareCase') {
        var doc2 = eval(uneval(doc)); //the inbound doc is immutable
        delete doc2.actions;
        delete doc2.xform_ids;
        emit(doc._id, doc2);
    }
}