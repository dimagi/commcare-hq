function (doc) {
    // !code util/mvp.js
    if (isChildCase(doc)) {

        function delivered_infacility(place, extra_no) {
            var i,
                result,
                arr = ["hospital", "facility", "centre", "post", "clinic", "yes"];
            if (extra_no) {
                arr.push("no", "home", "other", "road");
            }
            for (i=0; i < arr.length; i++) {
                result = arr[i];
                if (place && place.indexOf(result) >= 0) {
                    return true;
                }
            }
            return false;
        }

        var indicator_entries_open = {},
            indicator_entries_closed = {},
            indicators_dob_occured = {},
            indicators_dob = [];

        var status = (doc.closed) ? "closed" : "open";

        if (doc.dob || doc.dob_calc) {
            var dob_date = doc.dob_calc || doc.dob,
                weight_at_birth = doc.weight_at_birth,
                is_delivered = doc.delivered_in_facility === 'yes' || doc.delivered_in_facility === 'no' || delivered_infacility(doc.delivery_place, true) === true,
                is_delivered_in_facility = doc.delivered_in_facility === 'yes' || delivered_infacility(doc.delivery_place, false) === true,
                opened_on_date = new Date(doc.opened_on);

            if (is_delivered) {
                indicators_dob.push("dob delivered");
            }
            if (is_delivered_in_facility) {
                indicators_dob.push("dob delivered_in_facility");
            }

            indicators_dob_occured["occured_on"] = dob_date;
            indicator_entries_open["opened_on"] = dob_date;
            indicator_entries_open["opened_on "+status] = dob_date;
            if (weight_at_birth) {
                try {
                    var weight = parseFloat(weight_at_birth);
                    if (weight > 0) {
                        indicator_entries_open["opened_on weight_recorded"] = dob_date;
                    }
                    if (weight < 2.5) {
                        indicator_entries_open["opened_on low_birth_weight"] = dob_date;
                    }
                } catch (e) {
                    // pass
                }
            }


            emit_special(doc, opened_on_date, indicator_entries_open, [doc._id]);
            try {
                emit_standard(doc, new Date(dob_date), indicators_dob, [doc._id]);
                emit_special(doc, new Date(dob_date), indicators_dob_occured, [doc._id]);
            } catch (e) {
                // just in case the date parsing fails miserably.
            }

            if (doc.closed_on) {
                var closed_on_date = new Date(doc.closed_on);
                indicator_entries_closed["closed_on"] = dob_date;
                indicator_entries_closed["closed_on "+status] = dob_date;
                emit_special(doc, closed_on_date, indicator_entries_closed, [doc._id]);
            }
        }
    }
}
