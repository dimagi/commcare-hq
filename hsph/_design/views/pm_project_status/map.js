function(doc) {
    // !code util/hsph.js

    if (isHSPHForm(doc) &&
        (isDCOSiteLogReport(doc) || isCITLReport(doc) || isDCOBirthRegReport(doc) || isDCCFollowUpReport(doc) || isDCOFollowUpReport(doc) ) ){
        var info = doc.form.meta,
            entry = new HSPHEntry(doc);
        entry.getSiteInfo();
        entry.getBirthStats();
        entry.getCITLInfo();

        if (isDCOBirthRegReport(doc)  || isDCOFollowUpReport(doc)) {
            entry.data.outcomeDataType = true;
        } else if (isDCCFollowUpReport(doc)) {
            entry.data.processDataType = true;
        }

        entry.data.userId = info.userID;
        entry.data.DCTL = getDCTL(doc);

        if (entry.data.region) {
            emit([entry.data.IHFCHF, entry.data.region, entry.data.district, entry.data.siteNum, info.timeEnd], entry.data);
        }
    }
}