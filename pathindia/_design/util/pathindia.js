function isVisitForm (doc) {
    return (doc.xmlns === "http://openrosa.org/formdesigner/A20E32BC-1CBF-4870-A448-C59957098A48");
}

function isRegistrationForm (doc) {
    return (doc.xmlns === "http://openrosa.org/formdesigner/F7DAED3F-76AC-4DF0-8B8D-9F84E1408425");
}

function isWomanCaseType(doc) {
    return (doc.doc_type === 'CommCareCase'
        && doc.domain === 'pathindia'
        && doc.type === "woman");
}


var PathIndiaReport = function (doc) {
    var self = this;
    self.doc = doc;
    self.form = doc.form || doc;
    self.data = {};

    self.getAntenatalData = function () {
        var missed_period = (self.form.missed_period === 'yes'),
            pregnancy_confirmation = (self.form.pregnancy_confirmation === 'yes'),
            using_contraception = (self.form.using_contraception === 'yes'),
            anc_group_present = !!(self.form.anc_group);

        var anc = {};
        anc.pregnancy_status = false;
        anc.is_anc_visit = false;

        if ((missed_period || pregnancy_confirmation || using_contraception) && anc_group_present) {
            anc.is_anc_visit = true;
            anc.missed_period = missed_period;
            anc.pregnancy_confirmation = pregnancy_confirmation;
            anc.using_contraception = using_contraception;

            var anc_info = self.form.anc_group;

            anc.pregnancy_status = (anc_info.pregnancy_status === 'yes');

            anc.pregnancy_registration = (anc_info.pregnancy_registration === 'yes');
            anc.pregnancy_registration_place = anc_info.pregnancy_registration_place;
            anc.pregnancy_registration_date = anc_info.pregnancy_registration_date;
            anc.lmp = self.form.lmp;
            anc.anc_visit_count_to_date = anc_info.anc_visit_count_to_date;
            anc.most_recent_anc_visit_bp = (anc_info.most_recent_anc_visit_bp === 'yes');
            anc.most_recent_anc_visit_weight = (anc_info.most_recent_anc_visit_weight === 'yes');
            anc.most_recent_anc_visit_abdomen = (anc_info.most_recent_anc_visit_abdomen === 'yes');
            anc.anc_hemoglobin = (anc_info.anc_hemoglobin === 'yes');
            anc.hemoglobin_value = anc_info.hemoglobin_value;
            anc.tetanus_which_ones = anc_info.tetanus_which_ones;
            anc.how_many_ifa_total = anc_info.how_many_ifa_total;
            anc.injection_syrup_received = (anc_info.injection_syrup_received === 'yes');
            anc.anc_headache = (anc_info.anc_headache === 'yes');
            anc.anc_blurred_vision = (anc_info.anc_blurred_vision === 'yes');
            anc.anc_edema = (anc_info.anc_edema === 'yes');
            anc.anc_no_fetal_mvmt = (anc_info.anc_no_fetal_mvmt === 'yes');
            anc.anc_bleeding = (anc_info.anc_bleeding === 'yes');
            anc.delivery_place_determined = anc_info.delivery_place_determined;

            self.data.antenatal = anc;
        }
    };

    self.getIntranatalData = function () {
        var pregnancy_outcome = self.form.pregnancy_outcome,
            live_birth_questions_present = !!(self.form.live_birth_questions);

        if (pregnancy_outcome && live_birth_questions_present) {
            var inc = {};
            inc.pregnancy_outcome = pregnancy_outcome;

            var inc_info = self.form.live_birth_questions;

            inc.birth_place = inc_info.birth_place;
            inc.delivery_type = inc_info.delivery_type;
            inc.child_sex = inc_info.child_sex;
            inc.birth_weight = inc_info.birth_weight;

            self.data.intranatal = inc;
        }
    };

    self.getPostnatalData = function () {
        var pnc_data = self.form.live_birth_questions;

        if (pnc_data && (pnc_data.breastfeeding_outcome || pnc_data.pnc_checkup || pnc_data.pnc_complications)) {
            var pnc = {};

            pnc.breastfeeding_outcome = (pnc_data.breastfeeding_outcome === 'yes');
            pnc.pnc_checkup = pnc_data.pnc_checkup;
            pnc.pnc_complications = pnc_data.pnc_complications;
            pnc.jsy_received = (pnc_data.jsy_received === 'yes');

            self.data.postnatal = pnc;
        }


    };
};