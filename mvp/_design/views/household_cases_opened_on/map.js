function(doc) {
    if(doc.doc_type === "CommCareCase"
        && doc.type === 'household' ) {
        var definition = doc.computed_.mvp_indicators;
        var dobs = new Array(),
            deaths = new Array(),
            death_ids = new Array(),
            pregnancies = new Array();

        if (definition.case_child_close_reason.value) {
            for (var d in definition.case_child_close_reason.value) {
                var close_reason = definition.case_child_close_reason.value[d].value;
                if (close_reason === 'death') {
                    deaths.push(definition.case_child_close_reason.value[d]);
                    death_ids.push(definition.case_child_close_reason.value[d].case_id);
                }

            }
        }

        var ms_day = 24*60*60*1000;
        var ms_five_years = 5*365*ms_day,
            ms_31_days = 31*ms_day;

        if (definition.case_child_dob.value) {
            for (var c in definition.case_child_dob.value) {
                var dob_info = definition.case_child_dob.value[c];
                var dob = dob_info.value;
                if (dob) {
                    var dob_string = dob;
                    if (typeof dob_string !== 'string')
                        dob_string = dob.toDateString();

                    var baby_is_dead = death_ids.indexOf(dob_info.case_id) >= 0;

                    var neonate_until = new Date(dob_string),
                        under5_until = new Date(dob_string);

                    neonate_until.setTime(neonate_until.getTime() + ms_31_days);
                    under5_until.setTime(under5_until.getTime() + ms_five_years);

                    dobs.push({
                        case_id: dob_info.case_id,
                        case_closed: dob_info.case_closed,
                        case_opened: dob_info.case_opened,
                        value: dob_info.value,
                        is_dead: baby_is_dead,
                        neonate_until: neonate_until.toISOString(),
                        under5_until: under5_until.toISOString()
                    });
                }
            }
        }

        if (definition.case_pregnancy.value) {
            for (var p in definition.case_pregnancy.value) {
                var p_info = definition.case_pregnancy.value[p];
                var preg_end = p_info.case_closed;

                if (!preg_end && p_info.case_opened) {
                    var estimated_end = new Date(preg_end);
                    estimated_end.setTime(estimated_end.getTime() + 42*7*ms_day);
                    preg_end = estimated_end.toISOString();
                }
                if (preg_end && p_info.case_opened)
                    pregnancies.push({
                        case_id: p_info.case_id,
                        case_closed: preg_end,
                        case_opened: p_info.case_opened,
                        value: p_info.value
                    });
            }
        }

        if (doc.closed_on) {
            emit([doc.domain, "opened_on closed", doc.opened_on, doc._id], 1);
            emit([doc.domain, "closed_on closed", doc.closed_on, doc._id], 1);
            for (var i in dobs) {
                emit([doc.domain, "opened_on closed dob", doc.opened_on, doc._id], dobs[i]);
                emit([doc.domain, "closed_on closed dob", doc.closed_on, doc._id], dobs[i]);
            }
            for (var i in pregnancies) {
                emit([doc.domain, "opened_on closed pregnancy", doc.opened_on, doc._id], pregnancies[i]);
                emit([doc.domain, "closed_on closed pregnancy", doc.closed_on, doc._id], pregnancies[i]);
            }
        } else {
            emit([doc.domain, "opened_on open", doc.opened_on, doc._id], 1);
            for (var i in dobs)
                emit([doc.domain, "opened_on open dob", doc.opened_on, doc._id], dobs[i]);
            for (var i in pregnancies)
                emit([doc.domain, "opened_on open pregnancy", doc.opened_on, doc._id], pregnancies[i]);

        }
    }
}