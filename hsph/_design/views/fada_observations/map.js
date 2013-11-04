function (doc) {
    // !code util/hsph.js
    
    if (!isFADAProcessDataForm(doc)) {
        return;
    }

    // If you're trying to write an efficient report query in CouchDB with
    // map-reduce you might think that you could emit hashes of scalar values
    // from your map function and then sum the hashes into one hash in your
    // reduce function.  Unfortunately, CouchDB returns reduce_limit errors if
    // your reduce output is too big in the absolute, even if it's growing at an
    // acceptable rate / there's some requirement that the reduce output has to
    // be *smaller* than the input values.
    //
    // In order to avoid the prospect of having to split every value in the hash
    // into its own emitted value with a separate key, which would make querying
    // the report data slow as molasses, we just have this utility function that
    // splits the keys into n groups and emits n hashes.
    //
    // Note: this means that you have to explicitly set every key in each map
    // output, or else the splits won't work/be useful.  Oh wait, no it doesn't,
    // and that's awesome!
    Object.prototype.keys = function () {
        var keys = [];
        for (var k in this) {
            if (this.hasOwnProperty(k)) {
                keys.push(k);
            }
        }
        return keys;
    };
    function split_emit(key, data, n) {
        n = n || 2;
        var keys = data.keys(),
            interval = Math.ceil(keys.length / n);
        keys.sort();
        for (var i = 0; i < n; i++) {
            var split_data = {};
            for (var j = i*interval; j < (i+1)*interval && j < keys.length; j++) {
                split_data[keys[j]] = data[keys[j]];
            }
            emit(["split_" + i].concat(key), split_data);
        } 
    }

    var form = doc.form,
        fields = {
            1: [
                "maternal_temp",
                "maternal_bp",
                "partograph",
                "scc_used_pp1",
                "pp_1_birth_companion_present"
            ],
            2: [
                "maternal_temp_pp2",
                "maternal_bp_pp2",
                "oxycotin_started",
                "soap",
                "water",
                "gloves_used",
                "scc_used_pp2",
                "pp3_birth_companion_present"
            ],
            3: [
                "oxycotin",
                "baby_apneic",
                "baby_intervention",
                "pp_3_birth_companion_present"
            ],
            4: [
                "maternal_temp_pp4",
                "maternal_bp_pp4",
                "baby_wt",
                "baby_temp",
                "baby_placed_on_mother_abdomen",
                "breastfeeding",
                "scc_used_pp4",
                "pp_4_birth_companion_present"
            ]
        },
        checklist_options = [
            "picked_up_during_care",
            "looked_at_poster",
            "filled_out_after_care",
        ];

    var data = {
        total_forms: 1
    };

    // ensures that emit output has e.g.
    // pp1_maternal_temp = 1
    // for each of the above values if 
    // form.pause_point_1_observed == 'yes'
    // and form.pause_point_1_questions.maternal_temp == 'yes', otherwise
    // pp1_maternal_temp = 0.
    //
    // For checklist_options, ensures that e.g.
    // pp1_scc_usage_picked_up_during_care = 1
    // if form.pause_point_1_questions.scc_used_pp1 = 'yes'
    // and form.pause_point_1_questions.scc_usage_pp1 (a multiselect) contains
    // 'picked_up_during_care'.
    // We could just split the multiselect value and dynamically increment
    // counts, but this ensures that the report is coded exactly to spec, and
    // also that non-present values always get a 0 (which currently the
    // processing layer expects)
    for (var pp=1; pp <= 4; pp++) {
        var observed = (form["pause_point_" + pp + "_observed"] === 'yes'),
            questions = form["pause_point_" + pp + "_questions"];

        data["pp" + pp + "_observed"] = observed;

        for (var i = 0; i < fields[pp].length; i++) {
            var field = fields[pp][i];

            if (observed && questions) {
                data["pp" + pp + "_" + field] = (questions[field] === 'yes'); 
            } else {
                data["pp" + pp + "_" + field] = 0;
            }
        }

        if (pp !== 3) {
            for (var i = 0; i < checklist_options.length; i++) {
                var option = checklist_options[i],
                    key = "pp" + pp + "_scc_usage_" + option;

                if (observed && questions && questions["scc_used_pp" + pp] === 'yes') {
                    data[key] = (questions["scc_usage_pp" + pp].indexOf(option) !== -1);
                } else {
                    data[key] = 0;
                }
            }
        }
    }
        
    var medication_fields = [
        "oxycotin_admin",
        "ab_mother",
        "mgsulp",
        "ab_baby",
        "art_mother",
        "art_baby",
    ];

    // similar processing to pause point, except for the one-off form.medications
    // group
    data.medication_observed = (form.medication_observed === 'yes');

    for (var i = 0; i < medication_fields.length; i++) {
        var field = medication_fields[i];

        if (data.medication_observed && form.medications) {
            data["med_" + field] = (form.medications[field] === 'yes');
        } else {
            data["med_" + field] = 0;
        }
    }
    
    // used by secondary outcome report
    data.pp2_soap_and_water = (data.pp2_soap === 'yes' && data.pp2_water === 'yes');

    data.site_id = form.site_id;
    data.user_id = form.meta.userID;

    split_emit([doc.domain, "user", form.meta.userID, form.process_date_admission, form.process_sbr_no], data, 2);
    split_emit([doc.domain, "site", form.site_id, form.process_date_admission, form.process_sbr_no], data, 2);

}
