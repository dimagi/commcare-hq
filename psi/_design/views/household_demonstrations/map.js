function (doc) {
    //!code util/emit_array.js

    if (doc.doc_type === 'XFormInstance' && (doc.domain === 'psi' || doc.domain === 'psi-unicef')) {
        var form = doc.form;

        if (form["@name"] !== 'Household Demonstration') {
            return;
        }

        var data = {
            demonstrations: parseInt(form["hh_covered"], 10) || 0,
            children: parseInt(form["number_young_children_covered"], 10) || 0,
            leaflets: parseInt(form["leaflets_distributed"], 10) || 0,
            kits: parseInt(form["kits_sold"], 10) || 0
        };

        var opened_on = form.meta.timeEnd;

        var village = "" + (isNaN(form.activity_village) ? form.activity_village : parseInt(form.activity_village, 10))

        emit_array([doc.domain, form.activity_state, form.demo_type], [opened_on], data);
        emit_array([doc.domain, form.activity_state], [opened_on], data);
        emit_array([doc.domain, form.activity_state, form.activity_district, form.demo_type], [opened_on], data);
        emit_array([doc.domain, form.activity_state, form.activity_district], [opened_on], data);
        emit_array([doc.domain, form.activity_state, form.activity_district, form.activity_block, form.demo_type],
            [opened_on], data);
        emit_array([doc.domain, form.activity_state, form.activity_district, form.activity_block],
            [opened_on], data);
        emit_array([doc.domain, form.activity_state, form.activity_district, form.activity_block, village,
                form.demo_type], [opened_on], data);
        emit_array([doc.domain, form.activity_state, form.activity_district, form.activity_block, village],
            [opened_on], data);
    }
}
