// Emit the most recent date a case has been modified on by each sync token
function (doc) {
    if (doc.doc_type === 'CommCareCase') {
        var actions = doc.actions;
        for (var i = 0; i < actions.length; i += 1) {
            emit(doc._id, actions[i]['sync_log_id']);
        }
    }
}
