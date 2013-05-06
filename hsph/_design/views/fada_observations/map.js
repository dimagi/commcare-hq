function (doc) {
    // !code util/hsph.js
    
    if (!isFADAProcessDataForm(doc)) {
        return;
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
                "baby_wt",
                "baby_temp",
                "breastfeeding",
                "scc_used_pp4",
                "pp_4_birth_companion_present"
            ]
        },
        medication_fields = [
            "oxycotin_admin",
            "ab_mother",
            "mgsulp",
            "ab_baby",
            "art_mother",
            "art_baby",
            "antiobiotics_baby"
        ];

    var data = {
        total_forms: 1
    };

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
    }

    data.medication_observed = (form.medication_observed === 'yes');

    for (var i = 0; i < medication_fields.length; i++) {
        var field = medication_fields[i];

        if (data.medication_observed && form.medications) {
            data["med_" + field] = (form.medications[field] === 'yes');
        } else {
            data["med_" + field] = 0;
        }
    }

    emit(["user", form.meta.userID, form.process_date_admission, form.process_sbr_no], data);

    // used by secondary outcome report
    data.pp2_soap_and_water = (data.pp2_soap === 'yes' && data.pp2_water === 'yes');
    emit(["site", form.site_id, form.process_date_admission, form.process_sbr_no], data);

}
