function (doc) {
    if (doc.doc_type === 'CommCareCase') {
        var actions = doc.actions;
        for (var i = 0; i < actions.length; i++) {
            var action = actions[i];
            if (action.action_type === 'update') {
                var user = action.user_id;
                if (!user) {
                    user = doc.user_id;
                }
                emit(['ctable', action.date, doc.domain, user], 1);
                emit([doc.domain, user, action.date], 1);
            }
        }
    }
}