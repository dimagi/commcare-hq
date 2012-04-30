function isHSPHForm(doc) {
    return (doc.doc_type === 'XFormInstance'
            && doc.domain === 'hsph');
}

function isHSPHBirthCase(doc) {
    return (doc.doc_type === 'CommCareCase'
            && doc.domain === 'hsph'
            && doc.type === "birth");
}

function calcHSPHBirthDatespan(doc) {
    if (doc.date_delivery || doc.date_admission) {
        var date_del = (doc.date_delivery) ? new Date(doc.date_delivery) : new Date(doc.date_admission);
        return {
            start: new Date(date_del.getTime() + 8*24*60*60*1000),
            end: new Date(date_del.getTime() + 21*24*60*60*1000)
        };
    }
    return null;
}

function calcNumBirths(doc) {
    var info = (doc.form) ? doc.form : doc;
    if (info.mother_delivered_or_referred === "delivered") {
        return (info.multiple_birth === 'yes') ? parseInt(info.multiple_birth_number) : 1;
    }
    return 0;
}

function isDCOFollowUpReport(doc) {
    return (doc.xmlns === "http://openrosa.org/formdesigner/E5E03D8D-937D-46C6-AF8F-C1FD176E2E1B");
}

function isDCOBirthRegReport(doc) {
    return (doc.xmlns === "http://openrosa.org/formdesigner/FE77C4BD-38EE-499B-AC5E-D7279C83BDB5");
}

function isDCOSiteLogReport(doc) {
    return (doc.xmlns === "http://openrosa.org/formdesigner/8412C3D0-F06C-49BF-9067-ED62E991F315");
}

function isDCCFollowUpReport(doc) {
    return (doc.xmlns === "http://openrosa.org/formdesigner/A5B08D8F-139D-46C6-9FDF-B1AD176EAE1F");
}

function formatDCOSiteID(doc) {
    var info = (doc.form) ? doc.form : doc;
    if (info.site_id)
        return info.site_id;
    return "unknown"
}

function isContactProvided(doc) {
    var info = (doc.form) ? doc.form : doc;
    return !!(info.phone_mother === 'yes' ||
        info.phone_husband === 'yes' ||
        info.phone_house === 'yes' );
}

function getDCO(doc) {
    return doc.form.meta.userID;
}

function getDCTL(doc) {
    return "DCTL Unknown";
}