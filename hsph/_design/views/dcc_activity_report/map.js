function(doc) {
    // !code util/hsph.js

    if (isHSPHForm(doc) &&
        isDCCFollowUpReport(doc)) {
        var info = doc.form.meta,
            entry = new HSPHEntry(doc);
        entry.getBirthStats();
        entry.getFormLengthInfo();
        entry.getFollowUpStatus();

        entry.data.timeEnd = info.timeEnd;

        emit([info.userID, info.timeEnd], entry.data);
    }
}