function (doc) {
    //!code util/emit_array.js
    //!code util/repeats.js

    if (doc.doc_type === 'XFormInstance' && (doc.domain === 'psi' || doc.domain === 'psi-unicef')) {
        var form = doc.form;

        if (form["@name"] !== 'Sensitization Session') {
            return;
        }

        var data = {
            sessions: count_in_repeats(form.training_sessions, "number_of_blm_attended") +
                        get_repeats(form.training_sessions, function(data) {
                            return data['type_of_sensitization'] === 'vhnd';
                        }).length,
            ayush_doctors: count_in_repeats(form.training_sessions, "num_ayush_doctors"),
            mbbs_doctors: count_in_repeats(form.training_sessions, "num_mbbs_doctors"),
            asha_supervisors: count_in_repeats(form.training_sessions, "num_asha_supervisors"),
            ashas: count_in_repeats(form.training_sessions, "num_ashas"),
            awws: count_in_repeats(form.training_sessions, "num_awws"),
            other: count_in_repeats(form.training_sessions, "num_other"),
            attendees: count_in_repeats(form.training_sessions, "number_attendees")
        };

        var opened_on = form.meta.timeEnd;

        emit_array([form.training_state, form.training_district, form.training_block], [opened_on], data);
    }
}
