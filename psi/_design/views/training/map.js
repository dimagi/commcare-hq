function (doc) {
    //!code util/emit_array.js
    //!code util/repeats.js

    if (doc.doc_type === 'XFormInstance' && (doc.domain === 'psi' || doc.domain === 'psi-unicef')) {
        var form = doc.form;

        if (form["@name"] !== 'Training Session') {
            return;
        }

        var opened_on = form.meta.timeEnd;

        var trainee_categories = ['private', 'public', 'depot_holder', 'flw_training'];
        var category_key_slugs = {
            private: 'priv',
            public: 'pub',
            depot_training: 'dep',
            flw_training: 'flw'
        };

        var num_trained = function(doctor_type) {
            return get_repeats(form.trainee_information, function(data) {
                return data.doctor_type == doctor_type;
            }).length;
        };

        var tc = form.trainee_category;
        var slug = false;
        for (var i = 0; i < trainee_categories.length; i++) {
            if (tc === trainee_categories[i]) {
                slug = category_key_slugs[tc];
                break;
            }
        }

        if (slug) {
            var data = {};
            data[slug+"_trained"] = 1;

            if (tc === 'private' || tc === 'public') {
                data[slug+"_allo_trained"] = num_trained('allopathic');
                data[slug+"_ayush_trained"] = num_trained('ayush');
            }

            //scores
            var trainees = get_repeats(form.trainee_information, function(t) { return t; });
            var num_gt80 = 0;
            for (var i = 0; i < trainees.length; i++) {
                if (trainees[i].post_test_score >= 80) num_gt80++;

                // emit the score_diff for each repeat. We do this because we want an average and each form may
                // not have the same number of repeats and the reduce views' average wouldn't be correct,
                var score_diff = (trainees[i].post_test_score || 0) - (trainees[i].pre_test_score || 0);
                emit([form.training_state, form.training_district, slug+'_avg_diff', opened_on, i], score_diff);
            }
            data[slug+"_gt80"] = num_gt80;
            emit_array([form.training_state, form.training_district], [opened_on], data);
        }
    }
}
