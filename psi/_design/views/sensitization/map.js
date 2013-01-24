function (doc) {
    //!code util/emit_array.js
    //!code util/repeats.js

    if (doc.doc_type === 'XFormInstance' && (doc.domain === 'psi' || doc.domain === 'psi-unicef')) {
        var form = doc.form;

        if (form["@name"] !== 'Sensitization Session') {
            return;
        }

        var blocks = get_from_repeats(form.training_sessions, "training_block");
        for (var i = 0; i < blocks.length; i++) {
            var block = blocks[i];
            var rf_func = function(repeat) {
                return repeat['training_block'] === block;
            };
            var data = {
                sessions: count_in_repeats(form.training_sessions, "number_of_blm_attended", rf_func) +
                    get_repeats(form.training_sessions, function(data) {
                        return rf_func(data) && data['type_of_sensitization'] === 'vhnd'
                    }).length,
                ayush_doctors: count_in_repeats(form.training_sessions, "num_ayush_doctors", rf_func),
                mbbs_doctors: count_in_repeats(form.training_sessions, "num_mbbs_doctors", rf_func),
                asha_supervisors: count_in_repeats(form.training_sessions, "num_asha_supervisors", rf_func),
                ashas: count_in_repeats(form.training_sessions, "num_ashas", rf_func),
                awws: count_in_repeats(form.training_sessions, "num_awws", rf_func),
                other: count_in_repeats(form.training_sessions, "num_other", rf_func),
                attendees: count_in_repeats(form.training_sessions, "number_attendees", rf_func)
            };

            var opened_on = form.meta.timeEnd;

            emit_array([form.training_state, form.training_district, block], [opened_on], data);
        }
    }
}
