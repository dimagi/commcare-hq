function (doc) {
    // !code util/hsph.js
    
    function datePlusDays(string, daysToAdd) {
        var newDate = new Date(string);
        newDate.setDate(newDate.getDate() + daysToAdd);
        return newDate;
    }

    function isCATITLFollowUpForm(doc) {
        // CATI TL and CATI apps use two variants of the same form with the same
        // xmlns!  need to update this with CATI TL app id on
        // hsph-betterbirth-pilot-2 once that app is live.
        //
        // However, since different user types use the different apps, this
        // shouldn't matter too much.
        return (isCATIFollowUpForm(doc) &&
                doc.app_id === "0f2e43639223398c7c563c9da4d7cef9" ||   // hsph-dev
                doc.app_id === "asdfasdfasdf");
    }

    if (!(
        isNewHSPHBirthCase(doc) ||
        isCATITLFollowUpForm(doc)
    )) {
        return;
    }

    var data = {},
        form = doc.form,
        userID, date;

    if (isNewHSPHBirthCase(doc)) {
        userID = doc.user_id;
        date = doc.opened_on;

        data.birthsEscalated = (doc.cati_allocation === "cati_tl");
        data.birthsFollowedUp = (doc.closed_by === "cati_tl");
        
        emit(["timedOut", doc.domain, userID, date], {
            followUpsTimedOut: (
                doc.cati_allocation === "cati_manager" &&
                (!doc.closed_on || datePlusDays(doc.date_admission, 21) < doc.closed_on)
            )       
        });
    }

    if (isCATITLFollowUpForm(doc)) {
        userID = form.meta.userID;
        date = form.meta.timeEnd;

        data.followUpsTransferred = (form.last_status === "fida");
        data.followUpsWaitlisted = (form.last_status === "cati_tl_waitlist");
    }
    
    if (Object.getOwnPropertyNames(data).length) {
        emit(["all", doc.domain, userID, date], data);
    }

}
