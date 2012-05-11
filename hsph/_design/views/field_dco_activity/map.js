function(doc) {
    // !code util/hsph.js

    if (isHSPHForm(doc) &&
        (isDCOFollowUpReport(doc) || isDCOSiteLogReport(doc) || isDCOBirthRegReport(doc)) ){
        var info = doc.form.meta,
            entry = new HSPHEntry(doc);
        entry.getSiteInfo();

        if (isDCOBirthRegReport(doc)) {
            entry.data.birthReg = true;
            entry.getBirthStats();
            entry.getFormLengthInfo();
        } else if (isDCOFollowUpReport(doc))
            entry.getFollowUpStatus();

        emit([getDCO(doc), getDCTL(doc), info.timeEnd], entry.data);
    }
}