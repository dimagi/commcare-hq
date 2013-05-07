function(doc) {
    // !code util/hsph.js

    if (isHSPHForm(doc) &&
        isDCOBirthRegReport(doc) &&
        doc.form.mother_delivered_or_referred === "delivered"){
        var info = doc.form.meta,
            entry = new HSPHEntry(doc);

        entry.getBirthStats();
        entry.getSiteInfo();
        entry.getFormLengthInfo();

        emit([entry.data.region, entry.data.district, entry.data.siteNum, info.timeEnd], entry.data);
    }
}