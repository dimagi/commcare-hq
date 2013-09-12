function dateBreakdown(dateString, breakdown) {
    var date = new Date(dateString);
    var ret = new Array();
    for (i in breakdown) {
        var elem = breakdown[i];
        if (elem === 'y') {
            ret.push(date.getUTCFullYear());
        } else if (elem === 'm') {
            ret.push(date.getUTCMonth());
        } else if (elem === 'd') {
            ret.push(date.getUTCDay());
        }
    }
    return ret;
}

var domain = 'project'
function isCAREForm(doc) {
    return (doc.doc_type === 'XFormInstance'
        && doc.domain === domain
        && doc.form && doc.form.meta);
}

function isCARECase(doc) {
    return (doc.doc_type === 'CommCareCase'
        && doc.domain === domain);
}

function isCAREWomanCase(doc) {
    return isCARECase(doc) && doc.type === 'Woman'
}

function isRC_Enregistrement(doc) {
    return checkNs(doc, "http://openrosa.org/formdesigner/5A457301-7D57-4332-8CAC-44E17B5ADBB2");
}

function isRC_SuiviDeEnceinte(doc) {
    return checkNs(doc, "http://www.commcarehq.org/example/hello-world");
}

function isRC_Accouchement(doc) {
    return checkNs(doc, "http://openrosa.org/formdesigner/2BA7D4F1-E6F4-4EF2-9F00-5A02A28D9410");
}

function isRC_SuiviDeNouveau(doc) {
    return checkNs(doc, "http://openrosa.org/formdesigner/E93DB604-C511-463F-B0C2-25952C71A50F");
}

function isRC_SuiviDeAccouchee(doc) {
    return checkNs(doc, "http://openrosa.org/formdesigner/9D6BFE31-1613-4D10-8772-1AC3C6979004");
}

var ns_rc_reference = "http://openrosa.org/formdesigner/B1E6BBC1-ACD3-408B-B3AB-783153063D56";
function isRC_Reference(doc) {
    return checkNs(doc, ns_rc_reference);
}

var ns_rc_suivi_de_reference = "http://openrosa.org/formdesigner/A2EEC8AA-4761-4C68-BCFF-B6C0287DAA51";
function isRC_SuiviDeReference(doc) {
    return checkNs(doc, ns_rc_suivi_de_reference);
}

function isRC_FermerLeDossier(doc) {
    return checkNs(doc, "http://openrosa.org/formdesigner/09149C06-4933-4EF9-ACC6-40A966D05FD7");
}

var ns_as_accouchement = "http://openrosa.org/formdesigner/EF3DF425-CCCB-4768-8C8E-9E8DB9692F07";
function isAS_Accouchement(doc) {
    return checkNs(doc, ns_as_accouchement);
}

function isAS_BilanDesAnalysesLabo(doc) {
    return checkNs(doc, "http://openrosa.org/formdesigner/FDEE073D-A136-46D2-8BC8-66B54AA34C07");
}

function isAS_Counseling(doc) {
    return checkNs(doc, "http://openrosa.org/formdesigner/05651B2B-DEBA-4708-8D50-34582BAA64D4");
}

function isAS_Examen(doc) {
    return checkNs(doc, "http://openrosa.org/formdesigner/FEEB3365-DFED-4B61-898D-6E8B9BC3DC26");
}

function isAS_PlanDAccouchement(doc) {
    return checkNs(doc, "http://openrosa.org/formdesigner/D37C874D-4117-477D-B1DD-FD0DAFC27A1D");
}

function isAS_ClotureLeDossier(doc) {
    return checkNs(doc, "http://openrosa.org/formdesigner/FD88BB2B-5375-456A-921A-8C853FD1A429");
}

function isAS_CompleterEnregistrement(doc) {
    return checkNs(doc, "http://openrosa.org/formdesigner/EBAECEBF-E225-4464-BCC0-340E229C28AD");
}

var ns_as_contre_reference_dune_nouveau_ne = "http://openrosa.org/formdesigner/2f1d76d4d0fcec7b474239f5f209f705736d3bb0";
function isAS_ContreReferenceDunNouveauNe(doc) {
    return checkNs(doc, ns_as_contre_reference_dune_nouveau_ne);
}

var ns_as_contre_reference_dune_accouche = "http://openrosa.org/formdesigner/6581d0a691eef1d0ba97b9a41bd1fa9ebace5d23";
function isAS_ContreReferenceDuneAccouche(doc) {
    return checkNs(doc, ns_as_contre_reference_dune_accouche);
}

var ns_as_contre_reference_dune_femme_enceinte = "http://openrosa.org/formdesigner/10c78d5a567b53fc504dc1e6a4bdede14bf12040";
function isAS_ContreReferenceDuneFemmeEnceinte(doc) {
    return checkNs(doc, ns_as_contre_reference_dune_femme_enceinte);
}

function isAS_EnregistrementDeBase(doc) {
    return checkNs(doc, "http://openrosa.org/formdesigner/585ca2d786e0a26b0fdcddbbf992f5ab114d6824");
}

function isAS_CounselingLorsDeLaSortieDuCS(doc) {
    return checkNs(doc, "http://openrosa.org/formdesigner/cb780e6e3b40db0cff0e524741371466fc0210e0");
}

function isAS_EnregistrementduNouveauNe(doc) {
    return checkNs(doc, "http://openrosa.org/formdesigner/A4FCED7D-DC8B-470E-8FC6-D30ADE4131DE");
}

var ns_as_surveillanceLorsDeLaSortieDuCS = "http://openrosa.org/formdesigner/fb01c7e9a965c32a6aa73bac222e4c79c8bae40";
function isAS_SurveillanceLorsDeLaSortieDuCS(doc) {
    return checkNs(doc, ns_as_surveillanceLorsDeLaSortieDuCS);
}

var ns_as_surveillanceA15m = "http://openrosa.org/formdesigner/516AC5E5-0DC0-4CD9-96F8-6DAFCD11CA0F";
function isAS_SurveillanceA15m(doc) {
    return checkNs(doc, ns_as_surveillanceA15m);
}

var ns_as_surveillanceA6h = "http://openrosa.org/formdesigner/B3BBEF61-866D-4663-B9B9-EF484FC56478";
function isAS_SurveillanceA6h(doc) {
    return checkNs(doc, ns_as_surveillanceA6h);
}

function isAS_ReferenceAUnNiveauSuperieur(doc) {
    return checkNs(doc, "http://openrosa.org/formdesigner/9484c334281a914f73a7f8797d7378d069925e18");
}

function isAS_SuiviDUneReferenceUnNiveauSuperieur(doc) {
    return checkNs(doc, "http://openrosa.org/formdesigner/a6c69d4244d53e87f6279b7a5ac6c6255ebfce9c");
}

function checkNs(doc, ns) {
    return (doc.xmlns === ns || doc.xform_xmlns === ns || doc === ns);
}