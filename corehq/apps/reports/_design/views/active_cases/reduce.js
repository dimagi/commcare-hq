function(key, values) {
    var active_cases = [];
    var val = {};
    for(var i in values) {
        active_cases.push(values[i].active_cases);
    }
    return {user_id: values[0].user_id, active_cases: sum(active_cases)}
}