function(doc) {
    // !code util/hsph.js

    if (isHSPHForm(doc) &&
        isDCCFollowUpReport(doc) ) {
        var info = doc.form.meta,
            entry = new HSPHEntry(doc);
        entry.getBirthStats();
        entry.getSiteInfo();
        entry.getFormLengthInfo();
        entry.getFollowUpStatus();


        if (entry.data.dateBirth) {
            var msInDay = 24*60*60*1000,
                followupDate = new Date(info.timeEnd),
                birthDate = new Date(entry.data.dateBirth);
            var followupLag = followupDate.getTime() - birthDate.getTime();
            if (followupLag < 9*msInDay)
                entry.data.atDay8 = true;
            else if (followupLag >= 9*msInDay && followupLag < 14*msInDay)
                entry.data.between9and13 = true;
        }
        if (entry.data.region)
            emit([entry.data.region, entry.data.district, entry.data.siteNum, info.timeEnd], entry.data);
    }
}