function (doc) {
    //!code util/emit_array.js

    if (doc.doc_type === 'XFormInstance' && (doc.domain === 'psi' || doc.domain === 'psi-unicef')) {
        if (doc.form["@name"] !== 'Training Session') {
            return;
        }

        var form = eval(uneval(doc.form));
        
        var opened_on = form.meta.timeEnd;

        // format form correctly
        var sub_doc_names = {
            allopathic: ["allopathic_doctors"],
            ayush: ["ayush", "ayush_bams", "ayush_bhms", "ayush_bums", "ayush_dhms", "ayush_dams", "ayush_others"],
            depot_holder: ["depot_ngo", "depot_cbo", "depot_shg", "depot_others"],
            flw_training: ["flw_asha", "flw_anm", "flw_aww", "flw_asha_supervisor", "flw_others"]
        };

        var merge_sub_docs = function(doc_name, sub_docs) {
            var num_trained = 0;
            var total_pre_score = 0;
            var total_post_score = 0;
            var num_80_percent = 0;

            for (var i = 0; i < sub_docs.length; i++) {
                var tag = sub_docs[i];
                if (tag === "allopathic_doctors") {
                    tag = "allopathic";
                }
                var doc = form[tag];
                if (doc) {
                    var nt = (parseInt(doc[tag+"_number_trained"], 10)||0) + (parseInt(doc[tag+"_num_trained"], 10)||0);
                    num_trained += nt;
                    num_80_percent += parseInt(doc[tag+"_num_80_percent"], 10) || 0;
                    total_pre_score += (parseFloat(doc[tag+"_avg_pre_score"]) || 0) * nt;
                    total_post_score += (parseFloat(doc[tag+"_avg_post_score"]) || 0) * nt;
                }
            }

            return {
                num_trained: num_trained,
                avg_pre_score: total_pre_score / (num_trained || 1),
                avg_post_score: total_post_score / (num_trained || 1),
                avg_diff: (total_post_score - total_pre_score) / (num_trained || 1),
                num_80_percent: num_80_percent
            };
        };

        for (var key in sub_doc_names) {
            if (sub_doc_names.hasOwnProperty(key)) {
                form["_" + key] = merge_sub_docs(key, sub_doc_names[key]);
            }
        }

        var trainee_categories = ['private', 'public', 'depot_holder', 'flw_training'];
        var category_key_slugs = {
            private: 'priv',
            public: 'pub',
            depot_holder: 'dep',
            flw_training: 'flw'
        };

        // determine which slug or substring to use for the specific trainee_category
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
                var al_f = form["_allopathic"];
                var ay_f = form["_ayush"];
                var al_num = al_f["num_trained"];
                var ay_num = ay_f["num_trained"];
                data[slug+"_allo_trained"] = al_num;
                data[slug+"_ayush_trained"] = ay_num;
                data[slug+"_avg_diff"] = (al_f["avg_diff"] * al_num) + (ay_f["avg_diff"] * ay_num) / (al_num + ay_num || 1);
                data[slug+"_gt80"] = al_f["num_80_percent"] + al_f["num_80_percent"];
            }
            else {
                data[slug+"_pers_trained"] = form["_" + tc]["num_trained"];
                data[slug+"_avg_diff"] = form["_" + tc]["avg_diff"];
                data[slug+"_gt80"] = form["_"+tc]["num_80_percent"];
            }
            emit_array([form.training_state, form.training_district], [opened_on], data);
        }
    }
}
