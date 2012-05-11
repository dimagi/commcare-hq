function(doc) {
    // !code util/hsph.js

    if (isHSPHBirthCase(doc)
        && !doc.closed
        && doc.date_delivery ){
            var entry = new HSPHEntry(doc);
            entry.getSiteInfo();
            entry.getCaseInfo();
            entry.getBirthStats();
            emit([doc.user_id, entry.data.region, entry.data.district, entry.data.siteNum, entry.data.dateBirth], entry.data);
    }
}