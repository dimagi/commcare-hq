# coding=utf-8
from datetime import timedelta
from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter
from corehq.apps.reports.sqlreport import SqlTabularReport
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin, DatespanMixin
from couchexport.models import Format
from custom.tdh.filters import TDHDateSpanFilter

UNNECESSARY_FIELDS = ['doc_type', 'numerator', 'base_doc', 'save_direct_to_sql', 'domain']
INFANT_HEADERS_MAP = {
    'case_id': 'Unique ID',
    'dob': 'Date of Birth',
    'sex': 'Gender',
    'village': 'Village',
    'bcg': 'BCG',
    'tablet_login_id': 'CSPS',
    'author_id': 'Author ID',
    'author_name': 'Author',
    'visit_date': 'Consult Date',
    'consultation_type': 'Type of Consultation',
    'number': 'Number',
    'weight': 'Weight',
    'height': 'Height',
    'muac': 'MUAC',
    'temp': 'Temperature',
    'zscore_hfa': 'HfA (z)',
    'mean_hfa': 'HfA (%)',
    'zscore_wfa': 'WfA (z)',
    'mean_wfa': 'WfA (%)',
    'zscore_wfh': 'WfH (z)',
    'mean_wfh': 'WfH (%)',
    'infection_grave_treat_0': 'Ampicilline pré référence',
    'infection_grave_treat_1': 'Gentamicine pré référence',
    'infection_grave_treat_2': 'Phénobartital',
    'infection_grave_no_ref_treat_0': 'Ampicilline',
    'infection_grave_no_ref_treat_1': 'Gentamicine',
    'infection_grave_no_ref_treat_2': 'Phénobartital',
    'infection_grave_no_ref_treat_5': 'Phénobartital',
    'infection_locale_treat_0': 'Erytromycine Orale',
    'infection_locale_treat_1': 'Amoxiciline Orale',
    'maladie_grave_treat_0': 'Ampicilline pré référence',
    'maladie_grave_treat_1': 'Gentamicine pré référence',
    'inf_bac_qa': "Demander: Le nourrisson a-t-il eu des convulsions ?",
    'inf_bac_freq_resp': "Compter la fréquence respiratoire",
    'inf_bac_qc': "Rechercher : L'enfant a-t-il un tirage *sous-costal* grave (inspiratoire) ?",
    'inf_bac_qd': "Rechercher un battement des ailes du nez",
    'inf_bac_qe': "Ecouter si le nourrisson émet un geignement",
    'inf_bac_qf': "Palper la fontanelle pour sentir si elle est bombée",
    'inf_bac_qg': "Regarder s’il y a un écoulement de pus de l’oreille",
    'inf_bac_qh': "Regarder si l’ombilic est rouge ou suintant de pus",
    'inf_bac_qj': "Mesurer la température. Est-elle ?",
    'inf_bac_qk': "Rechercher les pustules cutanées. Sont-elles nombreuses ou sévères?",
    'inf_bac_ql': "L'enfant est-il normal, agité ou irritable, léthargique ou inconscient ?",
    'inf_bac_qm': "Regarder les mouvements du nourrisson : Bouge-t-il moins que la normale ?",
    'diarrhee_qa': "L'enfant a-t-il la diarrhée ?",
    'alimentation_qa': "Le nourrisson a-t-il des difficultés à se nourrir ?",
    'alimentation_qb': "Le nourrisson est-il nourri au sein ?",
    'alimentation_qc': "Si oui, combien de fois en 24 heures ?",
    'alimentation_qd': "Le nourrisson reçoit-il d’habitude d’autres aliments ou d’autres boissons ?",
    'alimentation_qf': "Le nourrisson peut-il bien prendre le sein?",
    'alimentation_qg': "Est-ce que le nourrisson tète efficacement ?",
    'alimentation_qh': "Regarder la bouche pour détecter des ulcérations ou plaques blanches (muguet).",
    'vih_qa': "Lymphadénopathie persistante généralisée",
    'vih_qb': "Hépatomégalie",
    'vih_qc': "Splénomégalie",
    'vih_qd': "Otite moyenne chronique / récurrente",
    'vih_qe': "Problèmes cutanéo-muqueux",
    'vih_qf': "Fièvre > 1 mois",
    'vih_qg': "Anémie",
    'vih_qh': "Pneumonie grave récurrente",
    'vih_qi': "Encéphalopathie",
    'vih_qj': "Sérologie mère",
    'vih_qk': "Muguet buccal (hors période néonatale)",
    'vih_ql': "PCR Enfant",
    'other_comments': "Autres problèmes de santé",
}

NEWBORN_HEADERS_MAP = {
    'case_id': 'Unique ID',
    'dob': 'Date of Birth',
    'sex': 'Gender',
    'village': 'Village',
    'bcg': 'BCG',
    'tablet_login_id': 'CSPS',
    'author_id': 'Author ID',
    'author_name': 'Author',
    'visit_date': 'Consult Date',
    'consultation_type': 'Type of Consultation',
    'number': 'Number',
    'weight': 'Weight',
    'height': 'Height',
    'muac': 'MUAC',
    'temp': 'Temperature',
    'zscore_hfa': 'HfA (z)',
    'mean_hfa': 'HfA (%)',
    'zscore_wfa': 'WfA (z)',
    'mean_wfa': 'WfA (%)',
    'zscore_wfh': 'WfH (z)',
    'mean_wfh': 'WfH (%)',
    'infection_grave_treat_0': 'Ampicilline pré référence',
    'infection_grave_treat_1': 'Gentamicine pré référence',
    'infection_grave_no_ref_treat_0': 'Ampicilline',
    'infection_grave_no_ref_treat_1': 'Gentamicine',
    'infection_locale_treat_0': 'Erytromycine Orale',
    'infection_locale_treat_1': 'Amoxiciline Orale',
    'incapable_nourrir_treat_0': 'Ampicilline pré référence	',
    'incapable_nourrir_treat_1': 'Gentamicine pré référence	',
    'inf_bac_qa': "Demander et regarder si le nourrisson a eu ou a actuellement des convulsions",
    'inf_bac_qb': "Le nouveau-né est-il *incapable* de s'alimenter ?",
    'inf_bac_freq_resp': "Compter la fréquence respiratoire",
    'inf_bac_qd': "Rechercher un tirage sous-costal grave",
    'inf_bac_qe': "Rechercher un geignement expiratoire",
    'inf_bac_qf': "Regarder les mouvements du nouveau- né",
    'inf_bac_qg': "Rechercher des pustules sur la peau",
    'inf_bac_qh': "Apprécier la température axilaire",
    'inf_bac_qi': "Rechercher un ictère grave",
    'inf_bac_qj': "Regarder l'ombilic. Est-il rouge ou purulent ?",
    'poids_qa': "Regarder le poids actuel de l'enfant (normal: p >= 2500g / faible: 1500g <= p < 2500g / "
                "très faible: p <1500g)",
    'inf_occ_qa': "Inspecter les yeux du nouveau-né. Sont-ils purulents ? Sont-ils enflés ?",
    'vih_qa': "Quel est l'état sérologique de la mère ?",
    'vih_qb': "Hépatomégalie",
    'vih_qc': "Splénomégalie",
    'vih_qd': "Infection de l'oreille",
    'vih_qe': "Signes d'infection cutanéo-muqueuse",
    'vih_qf': "Pneumonie grave",
    'vih_qg': "Faible poids de naissance",
    'alimentation_qa': "Le nourrisson a-t-il des difficultés à se nourrir ?",
    'alimentation_qb': "Le nourrisson est-il nourri au sein ?",
    'alimentation_qd': "Le nourrisson reçoit-il d’habitude d’autres aliments ou liquides en "
                       "plus du lait maternel ?",
    'alimentation_qf': "Regarder la bouche du nouveau-né pour détecter un muget",
    'alimentation_qg': "Regarder la bouche du nouveau-né pour détecter une malformation au niveau de la bouche",
    'other_comments': "	Autres problèmes de santé",
}

CHILD_HEADERS_MAP = {
    'case_id': 'Unique ID',
    'dob': 'Date of Birth',
    'sex': 'Gender',
    'village': 'Village',
    'bcg': 'BCG',
    'tablet_login_id': 'CSPS',
    'author_id': 'Author ID',
    'author_name': 'Author',
    'visit_date': 'Consult Date',
    'consultation_type': 'Type of Consultation',
    'number': 'Number',
    'weight': 'Weight',
    'height': 'Height',
    'muac': 'MUAC',
    'temp': 'Temperature',
    'zscore_hfa': 'HfA (z)',
    'mean_hfa': 'HfA (%)',
    'zscore_wfa': 'WfA (z)',
    'mean_wfa': 'WfA (%)',
    'zscore_wfh': 'WfH (z)',
    'mean_wfh': 'WfH (%)',
    'pneumonie_grave_treat_0': 'Ampicilline pré référence',
    'pneumonie_grave_treat_1': 'Gentamicine pré référence',
    'pneumonie_grave_treat_4': 'Diazepam Injectable',
    'pneumonie_grave_no_ref_treat_0': 'Ampicilline',
    'pneumonie_grave_no_ref_treat_1': 'Gentamicine',
    'pneumonie_grave_no_ref_treat_3': 'Diazepam Injectable',
    'pneumonie_grave_no_ref_treat_5': 'Ampicilline',
    'pneumonie_grave_no_ref_treat_6': 'Gentamicine',
    'pneumonie_treat_0': 'Amoxiciline Orale',
    'pneumonie_treat_1': 'Cotrimoxazole',
    'deshydratation_severe_pas_grave_perfusion_treat_3': 'Ringer au lactate - phase 1',
    'deshydratation_severe_pas_grave_perfusion_treat_4': 'Ringer au lactate - phase 1',
    'deshydratation_severe_pas_grave_perfusion_treat_5': 'Soluté isotonique - phase 1',
    'deshydratation_severe_pas_grave_perfusion_treat_6': 'Soluté isotonique - phase 1',
    'deshydratation_severe_pas_grave_perfusion_treat_8': 'Ringer au lactate - phase 2',
    'deshydratation_severe_pas_grave_perfusion_treat_9': 'Ringer au lactate - phase 2',
    'deshydratation_severe_pas_grave_perfusion_treat_10': 'Soluté isotonique - phase 2',
    'deshydratation_severe_pas_grave_perfusion_treat_11': 'Soluté isotonique - phase 2',
    'deshydratation_severe_pas_grave_perfusion_treat_15': 'Cotrimoxazole',
    'deshydratation_severe_pas_grave_perfusion_treat_16': 'Erytromycine Orale',
    'deshydratation_severe_pas_grave_sng_treat_2': 'Cotrimoxazole',
    'deshydratation_severe_pas_grave_sng_treat_3': 'Erytromycine Orale',
    'deshydratation_severe_pas_grave_sans_sng_sans_perfusion_treat_3': 'Cotrimoxazole',
    'deshydratation_severe_pas_grave_sans_sng_sans_perfusion_treat_4': 'Erytromycine Orale',
    'signes_deshydratation_treat_0': 'Sulfate de Zinc',
    'signes_deshydratation_treat_3': 'Solution de réhydratation orale plan B par SNG',
    'pas_deshydratation_treat_1': 'Sulfate de Zinc',
    'dysenterie_treat_1': 'Ciprofloxacine Orale',
    'dysenterie_treat_2': 'Métronidazole Oral',
    'dysenterie_treat_3': 'Sulfate de Zinc',
    'diahree_persistante_treat_0': 'Multivitamines',
    'diahree_persistante_treat_1': 'Sulfate de Zinc',
    'paludisme_grave_treat_0': 'Quinine IM - charge',
    'paludisme_grave_treat_1': 'Ampicilline pré référence',
    'paludisme_grave_treat_2': 'Gentamicine pré référence',
    'paludisme_grave_treat_4': 'Paracétamol Oral',
    'paludisme_grave_treat_5': 'Acetylsalicylate De Lysine',
    'paludisme_grave_treat_7': 'Chloramphénicol Huileux',
    'paludisme_grave_no_ref_treat_0': 'Quinine IM - charge',
    'paludisme_grave_no_ref_treat_1': 'Quinine IM - entretien',
    'paludisme_grave_no_ref_treat_2': 'Ampicilline',
    'paludisme_grave_no_ref_treat_3': 'Gentamicine',
    'paludisme_grave_no_ref_treat_5': 'Paracétamol Oral',
    'paludisme_grave_no_ref_treat_6': 'Chloramphénicol Huileux',
    'paludisme_simple_treat_1': 'Artémether + Luméfantrine',
    'paludisme_simple_treat_2': 'Artémether + Luméfantrine',
    'paludisme_simple_treat_3': 'Artésunate + Amodiaquine - Forme Nourrisson',
    'paludisme_simple_treat_4': 'Artésunate + Amodiaquine - Forme Petit Enfant',
    'paludisme_simple_treat_6': 'Paracétamol Oral',
    'rougeole_compliquee_treat_0': "Vitamine A - Capsules 200'000 UI",
    'rougeole_compliquee_treat_1': "Vitamine A - Capsules 100'000 UI",
    'rougeole_compliquee_treat_2': 'Cotrimoxazole',
    'rougeole_compliquee_treat_3': 'Amoxiciline Orale',
    'rougeole_complications_treat_0': "Vitamine A - Capsules 200'000 UI",
    'rougeole_complications_treat_1': "Vitamine A - Capsules 100'000 UI",
    'rougeole_treat_0': "Vitamine A - Capsules 200'000 UI",
    'rougeole_treat_1': "Vitamine A - Capsules 100'000 UI",
    'rougeole_treat_2': 'Cotrimoxazole',
    'rougeole_treat_3': 'Amoxiciline Orale',
    'antecedent_rougeole_treat_0': "Vitamine A - Capsules 200'000 UI",
    'antecedent_rougeole_treat_1': "Vitamine A - Capsules 100'000 UI",
    'mastoidite_treat_0': 'Ampicilline pré référence',
    'mastoidite_treat_1': 'Gentamicine pré référence',
    'mastoidite_treat_2': 'Paracétamol Oral',
    'infection_aigue_oreille_treat_0': 'Cotrimoxazole',
    'infection_aigue_oreille_treat_1': 'Paracétamol Oral',
    'anemie_grave_treat_0': 'Quinine IM - charge',
    'anemie_treat_0': 'Fer/Folate',
    'anemie_treat_1': 'Artémether + Luméfantrine',
    'anemie_treat_2': 'Artémether + Luméfantrine',
    'anemie_treat_3': 'Artésunate + Amodiaquine - Forme Nourrisson',
    'anemie_treat_4': 'Artésunate + Amodiaquine - Forme Petit Enfant',
    'anemie_treat_5': 'Mebendazole Oral',
    'anemie_treat_6': 'Albendazole',
    'mass_treat_2': "Vitamine A - Capsules 200'000 UI",
    'mass_treat_3': "Vitamine A - Capsules 100'000 UI",
    'mass_treat_4': 'Amoxiciline Orale',
    'mass_treat_5': 'Cotrimoxazole',
    'mass_treat_7': 'Mebendazole Oral',
    'mass_treat_8': 'Albendazole',
    'mam_treat_2': 'Mebendazole Oral',
    'mam_treat_3': 'Albendazole',
    'mam_treat_5': "Vitamine A - Capsules 200'000 UI",
    'mam_treat_6': "Vitamine A - Capsules 100'000 UI",
    'mam_treat_7': 'Fer/Folate',
    'pas_malnutrition_treat_2': "Vitamine A - Capsules 200'000 UI",
    'pas_malnutrition_treat_3': "Vitamine A - Capsules 100'000 UI",
    'vih_symp_confirmee_treat_1': 'Cotrimoxazole',
    'vih_symp_confirmee_treat_2': 'Cotrimoxazole',
    'vih_symp_confirmee_treat_4': 'Multivitamines',
    'vih_confirmee_treat_1': 'Cotrimoxazole',
    'vih_confirmee_treat_2': 'Cotrimoxazole',
    'vih_confirmee_treat_4': 'Multivitamines',
    'vih_symp_probable_treat_1': 'Cotrimoxazole',
    'vih_symp_probable_treat_2': 'Cotrimoxazole',
    'vih_symp_probable_treat_3': 'Multivitamines',
    'vih_possible_treat_1': 'Cotrimoxazole',
    'vih_possible_treat_2': 'Cotrimoxazole',
    'vih_possible_treat_3': 'Multivitamines',
    'paludisme_grave_tdr_negatif_treat_0': 'Ampicilline pré référence',
    'paludisme_grave_tdr_negatif_treat_1': 'Gentamicine pré référence',
    'paludisme_grave_tdr_negatif_treat_3': 'Paracétamol Oral',
    'paludisme_grave_tdr_negatif_treat_4': 'Acetylsalicylate De Lysine',
    'paludisme_grave_tdr_negatif_treat_6': 'Chloramphénicol Huileux',
    'boire': "Demander : l’enfant est-il *incapable* de boire ou de prendre le sein ?",
    'vomit': "Demander : l’enfant vomit-il *tout* ce qu’il consomme ?",
    'convulsions_passe': "Demander : l’enfant a-t-il eu des convulsions *récemment* ?",
    'lethargie': "Observer : l’enfant est-il léthargique ou inconscient ?",
    'convulsions_present': "Observer : l’enfant convulse t-il *actuellement* ?",
    'toux_presence': "L'enfant a-t-il la toux ou des *difficultés respiratoires* ?",
    'toux_presence_duree': "Depuis combien de jours ?",
    'freq_resp': "Compter la fréquence respiratoire",
    'tirage': "Rechercher : L'enfant a-t-il un tirage *sous-costal* (inspiratoire) ?",
    'stridor': "Écouter : l’enfant a-t-il un stridor ou un sifflement de la respiration (inspiration) ou un"
               " geignement (expiration)",
    'diarrhee': "Diarrhée",
    'diarrhee_presence': "L'enfant a-t-il la diarrhée ?",
    'diarrhee_presence_duree': "Depuis combien de jours ?",
    'sang_selles': "Y a-t-il du sang dans les selles ?",
    'conscience_agitation': "L'enfant est-il normal, agité ou irritable, léthargique ou inconscient ?",
    'yeux_enfonces': "Les yeux de l'enfant sont-ils enfoncés ?",
    'soif': "Offrir à boire à l’enfant : est-il incapable de boire ou boit-il difficilement? "
            "Ou boit-il avidement, est-il assoiffé ?",
    'pli_cutane': "Pincer la peau de l’abdomen. Le pli cutané s’efface-t-il lentement ou très lentement "
                  "(plus de 2 secondes) ?",
    'fievre_presence': "L'enfant a-t-il de la fièvre ?",
    'fievre_presence_duree': "Depuis combien de jours ?",
    'fievre_presence_longue': "Si depuis plus de 7 jours, la fièvre a-t-elle été présente tous les jours ?",
    'tdr': "Réaliser un TDR: quel est le résultat ?",
    'urines_foncees': "Signes de paludisme grave : L'enfant a t-il les urines foncées (Coca-Cola) ?",
    'saignements_anormaux': "Signes de paludisme grave : L’enfant a t-il eu des saignements ?",
    'raideur_nuque': "Signes de paludisme grave : Observer et rechercher une raideur de la nuque",
    'ictere': "Signes de paludisme grave : L'enfant a-t-il un ictère (yeux jaunes) ?",
    'choc': "Signes de paludisme grave : L'enfant est-il en choc (pouls rapide, extrémités froides) ?",
    'eruption_cutanee': "Signe de rougeole : L'enfant a-t-il une éruption généralisée de type rougeole ou eu une "
                        "rougeole au cours des 3 derniers mois ?",
    'ecoulement_nasal': "Signe de rougeole : L'enfant a-t-il un écoulement nasal ?",
    'yeux_rouge': "Signe de rougeole : L'enfant a-t-il les yeux rouges ?",
    'ecoulement_oculaire': "Signe de complication de rougeole : L'enfant a-t-il un écoulement oculaire de pus ?",
    'ulcerations': "Signe de complication de rougeole : L'enfant a-t-il des ulcérations dans la bouche ?",
    'cornee': "Signe de complication de rougeole : L'enfant a-t-il une opacité de la cornée ?",
    'oreille': "Affection de l'oreille",
    'oreille_probleme': "L'enfant a-t-il un problème à l'oreille ?",
    'oreille_douleur': "L'enfant a-t-il mal aux oreilles ?",
    'oreille_ecoulement': "Y-a- t-il un écoulement de pus ?",
    'oreille_ecoulement_duree': "Si oui, depuis combien de jours ?",
    'oreille_gonflement': "Rechercher un gonflement douloureux derrière l’oreille",
    'paleur_palmaire': "Observer et rechercher la pâleur palmaire",
    'oedemes': "Rechercher des oedèmes au niveau des deux pieds",
    'test_appetit': "Test d'appetit",
    'serologie_enfant': "Sérologie de l'enfant",
    'test_enfant': "Test virologique pour l'enfant",
    'pneumonie_recidivante': "Pneumonie récidivante",
    'diarrhee_dernierement': "Diarrhée au cours des 3 derniers mois",
    'candidose_buccale': "Candidose buccale",
    'hypertrophie_ganglions_lymphatiques': "Hypertrophie des ganglions lymphatiques et palpables à "
                                           "plus d’un endroit",
    'augmentation_glande_parotide': "Augmentation du volume de la glande parotide",
    'test_mere': "Test virologique pour la mère",
    'serologie_mere': "Sérologie de la mère",
    'other_comments': "Autres problèmes de santé",
    'vitamine_a': "L'enfant a t-il reçu de la vitamine A lors des 6 derniers mois?"
}


class TDHReport(SqlTabularReport, CustomProjectReport, ProjectReportParametersMixin, DatespanMixin):
    use_datatables = True
    emailable = False
    exportable = True
    export_format_override = Format.UNZIPPED_CSV
    fields = [ExpandedMobileWorkerFilter, TDHDateSpanFilter]
    fix_left_col = True

    @property
    def report_config(self):
        emw = [u.user_id for u in ExpandedMobileWorkerFilter.pull_users_and_groups(
            self.domain, self.request, True, True).combined_users]
        if self.datespan.enddate - timedelta(days=30) > self.datespan.startdate:
            self.datespan.startdate = self.datespan.enddate - timedelta(days=30)
        config = dict(
            domain=self.domain,
            startdate=self.datespan.startdate,
            enddate=self.datespan.enddate,
            emw=tuple(emw)
        )
        return config

    @property
    def data_provider(self):
        return None

    @property
    def headers(self):
        return self.data_provider.headers

    @property
    def rows(self):
        return self.data_provider.rows

    @property
    def fixed_cols_spec(self):
        return dict(num=3, width=350)

    @property
    def export_table(self):
        from custom.tdh.reports.child_consultation_history import ChildConsultationHistoryReport, \
            CompleteChildConsultationHistoryReport
        from custom.tdh.reports.infant_consultation_history import InfantConsultationHistoryReport, \
            CompleteInfantConsultationHistoryReport
        from custom.tdh.reports.newborn_consultation_history import NewbornConsultationHistoryReport, \
            CompleteNewbornConsultationHistoryReport

        if self.request_params['detailed'] and not isinstance(self, (
                CompleteNewbornConsultationHistoryReport, CompleteInfantConsultationHistoryReport,
                CompleteChildConsultationHistoryReport)):
            if isinstance(self, NewbornConsultationHistoryReport):
                return CompleteNewbornConsultationHistoryReport(
                    request=self.request, domain=self.domain).export_table
            elif isinstance(self, InfantConsultationHistoryReport):
                return CompleteInfantConsultationHistoryReport(
                    request=self.request, domain=self.domain).export_table
            elif isinstance(self, ChildConsultationHistoryReport):
                return CompleteChildConsultationHistoryReport(
                    request=self.request, domain=self.domain).export_table

        return [self._export_table(self.report_context['report_table']['headers'],
                                   self.report_context['report_table']['rows'])]

    def _export_table(self, headers, formatted_rows):
        def _unformat_row(row):
            return [col.get("sort_key", col) if isinstance(col, dict) else col for col in row]

        table = headers.as_export_table
        rows = [_unformat_row(row) for row in formatted_rows]
        replace = ''

        for k, v in enumerate(table[0]):
            if v != ' ':
                replace = v
            else:
                table[0][k] = replace
        table.extend(rows)

        return ['', table]
