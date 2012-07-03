//Lighter weight view doc that strips out actions and xform ids for efficient transfer to caselogic.py
function (doc) {
    if (doc.doc_type === 'CommCareCase') {
        var actions = doc.actions;
        for (var i = 0; i < actions.length; i += 1) {
            var action = {};
            action['server_date'] = actions[i]['server_date'];
            action['sync_log_id'] = actions[i]['sync_log_id'];
            action['seq'] = i;
            emit(doc._id, action);
        }
    }
}