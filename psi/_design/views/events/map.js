function (doc) {
    //!code util/emit_array.js
    if (doc.doc_type === 'XFormInstance' && (doc.domain === 'psi' || doc.domain === 'psi-unicef')) {
        var form = doc.form;

        if (form["@name"] !== 'Plays and Events') {
            return;
        }

        var data = {
            events: 1,
            males: parseInt(form.number_of_males, 10) || 0,
            females: parseInt(form.number_of_females, 10) || 0,
            attendees: parseInt(form.number_of_attendees, 10) || 0,
            leaflets: parseInt(form.number_of_leaflets, 10) || 0,
            gifts: parseInt(form.number_of_gifts, 10) || 0
        };

        var opened_on = form.meta.timeEnd;

        emit_array([doc.domain, form.activity_state], [opened_on], data);
        emit_array([doc.domain, form.activity_state, form.activity_district], [opened_on], data);
    }
}
