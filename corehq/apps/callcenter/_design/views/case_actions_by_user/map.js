function (doc) {
    if (doc.doc_type === "CommCareCase" && doc.actions[0].user_id){
        var actions = doc.actions;
        for(var i=0; i < actions.length; i++) {
            var action = actions[i];
            var user = action.user_id;
            emit([doc.domain, action.date, user, doc.type, action.action_type, doc._id], 1)
        }
    }
}