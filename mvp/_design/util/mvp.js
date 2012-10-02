var MVP_NAMESPACE = "mvp_indicators",
    MS_IN_DAY = 24*60*60*1000;

function isChildVisitForm(doc) {
    return (doc.doc_type === "XFormInstance"
        && doc.xmlns === 'http://openrosa.org/formdesigner/B9CEFDCD-8068-425F-BA67-7DC897030A5A');
}

function isHomeVisitForm(doc) {
    return (doc.doc_type === "XFormInstance"
        && doc.xmlns === 'http://openrosa.org/formdesigner/266AD1A0-9EAE-483E-B4B2-4E85D6CA8D4B');
}

function isHouseholdCase(doc) {
    return (doc.doc_type === "CommCareCase" && doc.type === 'household');
}

function get_indicators(doc) {
    return doc.computed_.mvp_indicators;
}

function get_age_from_dob(dob, date_diff) {
    // dob and date_diff are date strings
    var now,
        birth_date = new Date(dob);
    if (date_diff) {
        now = new Date(date_diff);
    } else {
        now = new Date();
    }
    if (now >= birth_date) {
        return (now.getTime() - birth_date.getTime())/(MS_IN_DAY*365);
    }
    return null;
}