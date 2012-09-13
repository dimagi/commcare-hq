function(doc) {
    // !code util/hsph.js

    if (isHSPHForm(doc) &&
        (isDCOBirthRegReport(doc) || isDCOFollowUpReport(doc) || isDCCFollowUpReport(doc)) ){
        var info = doc.form.meta,
            entry = new HSPHEntry(doc);
        entry.getSiteInfo();

        if (isDCOBirthRegReport(doc)) {
            entry.data.outcomeOnDischarge = true;
        }else if (isDCCFollowUpReport(doc) || isDCOFollowUpReport(doc)) {
            entry.data.outcomeOn7Days = true;
            entry.getFollowUpStatus();
        }
        entry.getBirthStats();
        entry.getOutcomeStats();

        if (entry.data.region) {
            // some old data has non-uppercase data here
            var region = entry.data.region.toUpperCase(),
                district = entry.data.district.toUpperCase();
        }

        if (entry.data.referredInBirth) {
            if (entry.data.region)
                emit(["site referred_in", region, district, entry.data.siteNum, info.timeEnd], entry.data);
            emit(["site_id referred_in", entry.data.siteId, info.timeEnd], entry.data);
        }

        if (entry.data.region)
            emit(["site", region, district, entry.data.siteNum, info.timeEnd], entry.data);
        emit(["site_id", entry.data.siteId, info.timeEnd], entry.data);

    }
}
