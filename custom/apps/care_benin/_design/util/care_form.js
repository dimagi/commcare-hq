function CareForm(doc) {
    var self = this;
    self.doc = doc;
    self.form = (doc.form) ? doc.form : doc;
    self.received_on = doc.received_on;
    self.user_data = {};
    self.village_data = {};
    self.outcome_data = {};

    self.by_village = function() {
        self.rc_suivi_de_reference();
        self.rc_fermer_le_dossier();
        self.rc_reference();
        self.as_examen();
        self.as_accouchement();
        self.as_contre_reference_aux_ralais();
        self.as_completer_enregistrement();
        self.danger_signs(true);

        // TODO: get village
        emit_array(['village'], [self.received_on], self.village_data);
    }

    self.by_user = function() {
        if (isAS_Examen(self.doc)) {
            var exclude = ['case', 'meta'];
            var not_containing = ['@', 'data_node', '#']
            var total = 0, non_blank = 0;
            for (var key in self.form) {
                if (self.form.hasOwnProperty(key) &&
                    not_containing.every(function(v) { return key.indexOf(v) === -1; }) &&
                    exclude.indexOf(key) === -1) {
                    total++;
                    if (self.form[key].trim()) {
                        non_blank++;
                    }
                }
            }
            self.user_data.cpn_exam_total = total;
            self.user_data.cpn_exam_answered = non_blank;
            self.user_data.cpn_exam_forms = 1;

            if (self.form.classifier_anemie_severe === 'oui' || self.form.classifier_anemie_modere === 'oui') {

                self.user_data.pregnant_anemia = 1;
            }
        } else if (isAS_CounselingLorsDeLaSortieDuCS(self.doc)) {
            if (self.form.demander_choisir_methode_PF === 'oui') {
                self.user_data.acceptants_for_fp = 1;
            }
        } else if (isAS_Accouchement(self.doc)) {
            if (self.form.etat_enfant === 'decedee') {
                self.user_data.stillborn = 1;
            }

            if (self.form.etat_mere === 'referee') {
                self.user_data.birth_complications_referred = 1;
            }
        } else if (isAS_CompleterEnregistrement(self.doc)) {
            if (self.form.Alerte_GARE === 'ok' || self.form.avis_mort_ne === 'ok') {
                self.user_data.high_risk_pregnancy = 1;
            }
        }

        emit_array([self.form.meta.userID], [self.received_on], self.user_data);
    }

    self.outcomes = function () {
        if (isAS_Accouchement(self.doc)) {
            self.outcome_data.birth_total = 1;
            if (self.form.question108 && self.form.question108.delivrance === 'GAPTA') {
                self.outcome_data.birth_gapta = 1;
            }
        }

        if (isRC_SuiviDeReference(self.doc)) {
            var ref = self.form.pas_de_contre_reference;
            var key = 'references_to_clinic_total_'+self.form.condition_data_node;
            if (ref && ref.es_tu_allee && ref.es_tu_allee === 'oui') {
                self.outcome_data[key] = 1;
            } else if (self.form.satisfait) {
                self.outcome_data[key] = 1;
            }
        }

        emit_array([], [self.received_on], self.outcome_data);
    }

    self.danger_signs = function (by_village) {
        if (isRC_Reference(self.doc)) {
            _emit_danger_signs('danger_sign_count_pregnancy', self.form.signe_danger_enceinte, by_village);
            _emit_danger_signs('danger_sign_count_accouchee', self.form.signe_danger_accouchee, by_village);
            _emit_danger_signs('danger_sign_count_birth', self.form.signe_danger_nne, by_village);
        }
    }

    self.rc_suivi_de_reference = function () {
        if (isRC_SuiviDeReference(self.doc)) {

            self.village_data.reference_to_clinic = 1;

            var ref = self.form.pas_de_contre_reference;
            if (ref && ref.es_tu_allee && ref.es_tu_allee === 'oui') {
                self.village_data.reference_to_clinic_went = 1;
            }
        }
    }

    self.rc_fermer_le_dossier = function () {
        if (isRC_FermerLeDossier(self.doc)) {
            switch (self.form.raison) {
                case 'grossesse_echouee':
                    self.village_data.pregnancy_failed = 1;
                    break;
                case 'enc_morte':
                case 'acc_morte':
                case 'acc_et_nne_morts':
                    self.village_data.maternal_death = 1;
                    break;
            }

            if (self.form['nne-mort_age_jours'] < 7) {
                self.village_data.child_death_7_days = 1;
            }
        }
    }

    self.rc_reference = function () {
        if (isRC_Reference(self.doc)) {
            var condition = self.form.condition_data_node;
            if (condition === 'enceinte') {
                self.village_data.referral_per_type_enceinte = 1;
            } else if (condition === 'accouchee') {
                if (self.form.lequel_referer === 'mere') {
                    self.village_data.referral_per_type_accouchee = 1;
                } else if (self.form.lequel_referer === 'bebe') {
                    self.village_data.referral_per_type_nouveau_ne = 1;
                }
            }
        }
    }

    self.as_completer_enregistrement = function() {
        if (isAS_CompleterEnregistrement(self.doc)) {
            if (self.form.Alerte_GARE === 'ok' || self.form.avis_mort_ne === 'ok') {
                self.village_data.high_risk_pregnancy = 1;
            }
        }
    }

    self.as_contre_reference_aux_ralais = function () {
        if (isAS_ContreReferenceDuneFemmeEnceinte(self.doc) ||
            isAS_ContreReferenceDunNouveauNe(self.doc) ||
            isAS_ContreReferenceDuneAccouche(self.doc)) {

            self.village_data.referrals_transport_total = 1;
            if (self.form.moyen_transport) {
                self.village_data['referrals_transport_'+self.form.moyen_transport] = 1;
            }
        }
    }

    self.as_examen = function () {
        if (isAS_Examen(self.doc)) {
            if (self.form.classifier_anemie_severe === 'ok' || self.form.classifier_anemie_modere === 'ok'){
                self.village_data.anemic_pregnancy = 1;
            }
        }
    }

    self.as_accouchement = function () {
        if (isAS_Accouchement(self.doc)) {
            if (self.form.etat_enfant === 'decedee') {
                self.village_data.stillborn = 1;
            }

            if (self.form.etat_mere === 'decedee') {
                self.village_data.maternal_death = 1;
            }
        }
    }

    function _emit_danger_signs(key, danger_signs, by_village) {
        if (!danger_signs) {
            return;
        }
        var signs = danger_signs.trim().split(" ");
        for (var i = 0, len = signs.length; i < len; i++) {
            var s = signs[i];
            if (s) {
                if (by_village) {
                    self.village_data[key] = 1;
                } else {
                    emit(['danger_sign', s, self.received_on], 1);
                }
            }
        }
    }
}