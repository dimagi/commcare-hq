function (doc) {

    if (doc.domain != "pact") {
        return;
    }


    function get_case_id(doc) {
        if (doc.form['case'] !== undefined) {
            if (doc.form['case']['case_id'] !== undefined) {
                return doc.form['case']['case_id'];
            }
            else if (doc.form['case']['@case_id'] !== undefined) {
                return doc.form['case']['@case_id'];
            }
        }
        return null;
    }

    //this indexes by the observed date the dots observations
    function padzero(n) {
        return n < 10 ? '0' + n : n;
    }

    function pad2zeros(n) {
        if (n < 100) {
            n = '0' + n;
        }
        if (n < 10) {
            n = '0' + n;
        }
        return n;
    }

    function toISOString(d) {
        //source: http://williamsportwebdeveloper.com/cgi/wp/?p=503
        return d.getUTCFullYear() + '-' + padzero(d.getUTCMonth() + 1) + '-' + padzero(d.getUTCDate()) + 'T' + padzero(d.getUTCHours()) + ':' + padzero(d.getUTCMinutes()) + ':' + padzero(d.getUTCSeconds()) + '.' + pad2zeros(d.getUTCMilliseconds()) + 'Z';
    }

    function do_observation(doc, observe_date, anchor_date, drug_arr, obs_dict) {
        //previously from using anchor_date, used observed_date, but pact wanted the anchor date to drive the date bounds.

        var case_id = get_case_id(doc);
        if (drug_arr.length >= 2) {
        //if (drug_arr.length >= 2 && drug_arr[0] != 'unchecked') {
            obs_dict['adherence'] = drug_arr[0];
            obs_dict['method'] = drug_arr[1];
            if (drug_arr.length > 2) {
                obs_dict['day_note'] = drug_arr[2];
            }
            if (drug_arr.length > 3) {
                obs_dict['day_slot'] = drug_arr[3];
            }
            emit([case_id, 'anchor_date', anchor_date.getFullYear(), anchor_date.getMonth() + 1, anchor_date.getDate()], obs_dict);
            emit([case_id, 'observe_date', observe_date.getFullYear(), observe_date.getMonth() + 1, observe_date.getDate()], eval(uneval(obs_dict)));
            emit([anchor_date.getFullYear(), anchor_date.getMonth() + 1, anchor_date.getDate()], eval(uneval(obs_dict)));
            emit(['doc_id', doc._id], eval(uneval(obs_dict)));
        }
    }

    function parse_date(date_string) {
        if (!date_string) return new Date(1970, 1, 1);
        // hat tip: http://stackoverflow.com/questions/2587345/javascript-date-parse
        var parts = date_string.match(/(\d+)/g);
        // new Date(year, month [, date [, hours[, minutes[, seconds[, ms]]]]])
        return new Date(parts[0], parts[1] - 1, parts[2]); // months are 0-based, subtract fromour encoutner date
    }

    function getkeys(obj) {
        var keys = [];
        for (var key in obj) {
            if (obj.hasOwnProperty(key)) { //to be safe
                keys.push(key);
            }
        }
        return keys;
    }


    //function to emit all the dots observations into a format that's readable by the dotsview app
    if (doc.doc_type == "XFormInstance" && doc.xmlns == "http://dev.commcarehq.org/pact/dots_form") {
        var pactdata = doc['pact_dots_data_'];
        if (pactdata['dots'] !== undefined) {
            var anchor_date = new Date(pactdata['dots']['anchor']); //this is in num 3lettermonth YYYY
            var daily_data = pactdata['dots']['days'];
            var drop_note = true;
            var encounter_date = parse_date(doc.form['encounter_date']); //yyyy-mm-dd which sucks at parsing with new Date
            var anchor_datestring = anchor_date.getFullYear() + "-" + padzero(anchor_date.getMonth() + 1) + "-" + padzero(anchor_date.getDate());

            if (anchor_datestring == doc.form['encounter_date']) {
                for (var i = 0; i < daily_data.length; i += 1) {
                    //iterate through each day = i
                    //i = 0 = oldest
                    //i = length-1 = youngest, ie, today
                    var day_delta = daily_data.length - 1 - i;
                    var drug_classes = daily_data[i];
                    //var observed_date = new Date(anchor_date.getTime() - (24*3600*1000 * i));
                    var observed_date = new Date(pactdata['dots']['anchor']); //set value based upon anchor...
                    observed_date.setDate(anchor_date.getDate() - day_delta); //adjusted with the day_delta
                    for (var j = 0; j < drug_classes.length; j += 1) {
                        //iterate through the drugs to get art status within a given day.  right now that's just 2
                        var dispenses = drug_classes[j]; //right now just 2 elements[art, nonart]
                        var is_art = false;
                        if (j == 0) {
                            //non art drug is always zero'th
                            is_art = false;
                        }
                        else {
                            is_art = true;
                        }
                        var note = '';
                        if (i == daily_data.length - 1 && drop_note) {
                            //if this is the first element at the anchor date, put the note of the xform in here.
                            note = doc.form['notes'];
                            drop_note = false;
                        }

                        for (var drug_freq = 0; drug_freq < dispenses.length; drug_freq += 1) {
                            //within each drug, iterate through the "taken time", as according to frequency
                            //populate the rest of the information
                            //create the dictionary to be emitted
                            var drug_obs = {};
                            drug_obs['doc_id'] = doc._id;
                            drug_obs['pact_id'] = doc.form['pact_id'];
                            drug_obs['provider'] = doc.form['meta']['username'];
                            drug_obs['created_date'] = doc.form['meta']['timeStart'];
                            drug_obs['encounter_date'] = toISOString(encounter_date);
                            drug_obs['completed_date'] = doc.form['meta']['timeEnd'];
                            drug_obs['anchor_date'] = toISOString(anchor_date);
                            drug_obs['day_index'] = day_delta;
                            drug_obs['is_art'] = is_art;
                            drug_obs['note'] = note;
                            drug_obs['total_doses'] = dispenses.length;
                            drug_obs['observed_date'] = toISOString(observed_date);
                            drug_obs['dose_number'] = drug_freq;
                            do_observation(doc, observed_date, anchor_date, dispenses[drug_freq], drug_obs);
                        }
                    }
                }
            }
            else {
                //if (anchor_datestring != doc.form['encounter_date']) {
                //finally, if the observed_date and anchor dates are different, we need to make a manual single DOT entry:
                //doing a direct string interpretation due to timezone issues, at the time of creation on the phone, the DATE is correct, regardless of time taken.  So comparing by the individual
                //date components is the most accurate way to fly here.



                var new_drug_obs = {};
                new_drug_obs['doc_id'] = doc._id;
                //new_drug_obs['patient'] = doc.form['case']['case_id'];
                new_drug_obs['pact_id'] = doc.form['pact_id'];
                new_drug_obs['provider'] = doc.form['meta']['username'];
                new_drug_obs['created_date'] = doc.form['meta']['timeStart'];
                new_drug_obs['encounter_date'] = toISOString(encounter_date);
                new_drug_obs['observed_date'] = toISOString(encounter_date);
                new_drug_obs['completed_date'] = doc.form['meta']['timeEnd'];
                new_drug_obs['anchor_date'] = toISOString(encounter_date);
                new_drug_obs['day_index'] = -1;
                var day_note = "No check, from form";
                //new_drug_obs['day_note'] = "No check, from form";

                function generate_day_data(build_obs, is_art, form_obs, static_block) {
                    //reconstruct the full day of a submission based upon the preload regimen values
                    //if the form data is already submitted, then form_obs will be the "slot"
                    //in the static_art_dose_data index, so we skip over that.
                    var static_slots = ['a', 'b', 'c', 'd'];
                    var int_regimen = 0;
                    if (is_art) {
                        int_regimen = parseInt(doc.form['preload']['artregimen']);
                    } else {
                        int_regimen = parseInt(doc.form['preload']['nonartregimen']);
                    }

                    for (var r = 0; r < int_regimen; r++) {
                        var slot = static_slots[r];
                        var dose = static_block[slot]['dose'];
                        if (dose !== undefined) {
                            var patlabel = -1;
                            if (dose['patlabel'] !== undefined) {
                                patlabel = parseInt(dose['patlabel']);
                            }
                            //now see if the box is filled out
                            build_obs['is_art'] = is_art;
                            build_obs['total_doses'] = int_regimen;
                            var unchecked = ["unchecked","pillbox",day_note, patlabel];

                            if (r != form_obs) {
                                do_observation(doc, encounter_date, encounter_date, unchecked, eval(uneval(build_obs)));
                            }
                        }
                    }
                }

                function determine_day_slot(dose_data, selected_idx) {
                    //dose_data = doc.form['static_non_art_dose_data'] | doc.form['static_art_dose_data']
                    var dosekeys = getkeys(dose_data);
                    for (var q = 0; q < dosekeys.length; q++) {
                        var k = dosekeys[q];
                        var dose_data_val = dose_data[k];
                        if (dose_data_val['v'] == selected_idx) {
                            //verify that v == selected_idx
                            if (dose_data_val['dose'] != undefined) {
                                if (dose_data_val['dose']['patlabel'] != "") {
                                    return parseInt(dose_data_val['dose']['patlabel']);
                                }
                            }
                        }
                    }
                    return -1;
                }


                function emit_form_pillbox_obs(is_art, form_obs) {

                    var regimen_type = "";
                    var regimen_box = "";
                    var static_key = "";
                    var now_key = "";
                    if (is_art) {
                        regimen_type = "artregimen";
                        regimen_box = "artbox";
                        static_key = "static_art_dose_data";
                        now_key = "artnow";
                    } else {
                        regimen_type = "nonartregimen";
                        regimen_box = "nonartbox";
                        static_key = "static_non_art_dose_data";
                        now_key = "nonartnow";
                    }
                    form_obs['is_art'] = is_art;
                    form_obs['total_doses'] = parseInt(doc.form['preload'][regimen_type]);
                    form_obs['dose_number'] = parseInt(doc.form['pillbox_check'][regimen_box]);

//                    if (emit_day_slot >= 0) {
//                        form_obs['day_slot'] = emit_day_slot;
//                    }

                    form_obs['observed_date'] = toISOString(encounter_date);
                    var form_dispense = eval(doc.form['pillbox_check'][now_key]);
                    if (form_dispense !== undefined) {
                        form_dispense.push(day_note);

                        var emit_day_slot = determine_day_slot(doc.form[static_key], parseInt(doc.form['pillbox_check'][regimen_box]));
                        form_dispense.push(emit_day_slot);
                        do_observation(doc, encounter_date, encounter_date, form_dispense, eval(uneval(form_obs)));
                        return form_obs['dose_number'];
                    }
                    return -1;
                }


                var non_art_submit = emit_form_pillbox_obs(false, new_drug_obs);
                generate_day_data(new_drug_obs, false, non_art_submit, doc.form['static_non_art_dose_data']);

                var art_submit = emit_form_pillbox_obs(true, new_drug_obs);
                generate_day_data(new_drug_obs, true, art_submit, doc.form['static_art_dose_data']);



            }
        }
    }
    else if (doc.doc_type == "CObservationAddendum") {
        //if it's a reconciliation object, then unpack the internal individual entries and emit them one by one.
        for (var i = 0; i < doc.art_observations.length; i++) {
            var obs = eval(uneval(doc.art_observations[i])); //we will be mutating this object to emit it.  couchdb 1.0.2 seems to be really strict about non mutation of things you emit.
            var anchor_date = parse_date(obs.anchor_date);
            var observe_date = parse_date(obs.observed_date);
            obs['doc_id'] = doc._id;

            emit([obs.pact_id, 'anchor_date', anchor_date.getFullYear(), anchor_date.getMonth() + 1, anchor_date.getDate()], obs);
            emit([obs.pact_id, 'observe_date', observe_date.getFullYear(), observe_date.getMonth() + 1, observe_date.getDate()], eval(uneval(obs)));
            emit([observe_date.getFullYear(), observe_date.getMonth() + 1, observe_date.getDate()], eval(uneval(obs)));
        }
        for (var i = 0; i < doc.nonart_observations.length; i++) {
            var obs = eval(uneval(doc.nonart_observations[i]));
            var anchor_date = parse_date(obs.anchor_date);
            var observe_date = parse_date(obs.observed_date);
            obs['doc_id'] = doc._id;

            emit([obs.pact_id, 'anchor_date', anchor_date.getFullYear(), anchor_date.getMonth() + 1, anchor_date.getDate()], obs);
            emit([obs.pact_id, 'observe_date', observe_date.getFullYear(), observe_date.getMonth() + 1, observe_date.getDate()], eval(uneval(obs)));
            emit([observe_date.getFullYear(), observe_date.getMonth() + 1, observe_date.getDate()], eval(uneval(obs)));
        }
    }
}
