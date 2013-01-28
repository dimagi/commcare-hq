function (doc) {
    //!code util/emit_array.js
    //!code util/repeats.js

    if (doc.doc_type === 'XFormInstance' && (doc.domain === 'psi' || doc.domain === 'psi-unicef')) {
        var form = doc.form;

        if (form["@name"] !== 'Sensitization Session') {
            return;
        }

        var data = {
            sessions: parseInt(form["number_of_blm_attended"], 10) || 0,
            ayush_doctors: parseInt(form["num_ayush_doctors"], 10) || 0,
            mbbs_doctors: parseInt(form["num_mbbs_doctors"], 10) || 0,
            asha_supervisors: parseInt(form["num_asha_supervisors"], 10) || 0,
            ashas: parseInt(form["num_ashas"], 10) || 0,
            awws: parseInt(form["num_awws"], 10) || 0,
            other: parseInt(form["num_other"], 10) || 0,
            attendees: parseInt(form["number_attendees"], 10) || 0
        };

        var opened_on = form.meta.timeEnd;

        emit_array([form.training_state, form.training_district, form.training_block], [opened_on], data);
    }
}
