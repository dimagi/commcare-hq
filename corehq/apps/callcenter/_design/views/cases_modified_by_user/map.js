function (doc) {
    if (doc.doc_type === "CommCareCase" && doc.actions[0].user_id){
        var seenUsers = new Array();
        var actions = doc.actions;
        for(var i=actions.length-1; i >= 0; i--) {
            var action = actions[i];
            var user = action.user_id;
            if (user && seenUsers.indexOf(user) === -1) {
                seenUsers.push(user);
                emit([doc.domain, action.date, user, doc.type], 1)
            }
        }
    }
}