function (keys, values) {
    var lsd = "0";
    var count = 0;
    var device_ids = values[0].device_ids;
    for(var i in values) {
        var date = String(values[i].last_submission_date);
        count += values[i].count;
        if(date > lsd) {
            lsd = date;
        }
        if(i != 0) {
            for(var device_id in values[i].device_ids) {
                device_ids[device_id] = null;
            }
        }
    }
    return {
        count: count,
        last_submission_date: lsd,
        username: values[0].username,
        device_ids: device_ids
    };
}