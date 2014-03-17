function (doc) {
    //PACT specific view for the case computed_ stored weeklys chedules.
    //key: username (no domain)
    //value: day of week, pact_id (patient), active_date, ended_date, index

    var days = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
    if (doc.doc_type == "CommCareCase" && doc.domain == "pact") {
        //check to see it has a computed block and there are schedules in it.
        if (doc['computed_'] !== undefined) {
            if (doc['computed_']['pact_weekly_schedule'] !== undefined) {
                var schedules = doc['computed_']['pact_weekly_schedule'];
                for (var i = 0; i < schedules.length; i++) {
                    var schedule = schedules[i];
                    for (var j = 0; j < days.length; j++) {
                        var username = schedule[days[j]];
                        if (username == null) {
                            continue;
                        }
                        else {
                            //username, day_of_week-> (pact_id, active_date)
                            var emission = {};
                            emission['day_of_week'] = j;
                            emission['case_id'] = doc._id;
                            emission['active_date'] = schedule.started;
                            emission['ended_date'] = schedule.ended;
                            emission['schedule_index'] = i;
                            emit(username, emission);
                        }
                    }
                }
            }
        }
    }
}