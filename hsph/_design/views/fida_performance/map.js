function(doc) {
    // !code util/hsph.js
    // !code util/hsph_field_management.js

    if (!(
        isFIDALogSiteForm(doc) ||
        isHSPHBirthRegForm(doc) || 
        isCATIFollowUpForm(doc) ||
        isNewHSPHBirthCase(doc))) 
    {
        return;
    } 
    
    function daysSinceEpoch(date) {
        return Math.floor(date.getTime() / (24 * 3600 * 1000));
    }
    
    function datePlusDays(string, daysToAdd) {
        var newDate = new Date(string);
        newDate.setDate(newDate.getDate() + daysToAdd);
        return newDate;
    }
    
    var data = {},
        form = doc.form,
        date, userID;
    
    if (form) {
        date = form.meta.timeEnd.substring(0, 10);
        userID = form.meta.userID;
    } else {
        date = doc.opened_on.substring(0, 10);
        userID = doc.user_id;
    }
    
    if (isFIDALogSiteForm(doc)) {
        data.facilityVisits = 1;
        data[form.current_site + 'Visits'] = 1;
    } else if (isHSPHBirthRegForm(doc)) {
        data = getContactData(form);
        data.birthRegistrations = 1;
        data.birthRegistrationTime = get_form_filled_seconds(doc);
    } else if (isCATIFollowUpForm(doc)) {
        data.homeVisitsCompleted = (form.last_status === 'followed_up'); 
        emit(["workingDays", doc.domain, userID, date], {
            workingDay: daysSinceEpoch(new Date(form.meta.timeEnd))
        });
    }

    if (Object.getOwnPropertyNames(data).length) {
        emit(["all", doc.domain, userID, date], data);
    }

    if (isNewHSPHBirthCase(doc)) {
        emit(["assigned", doc.domain, userID, date], {
            homeVisitsAssigned: (!doc.closed_on || datePlusDays(doc.date_admission, 21) < doc.closed_on)
        });
        
        emit(["open30Days", doc.domain, userID, date], {
            homeVisitsOpenAt30Days: (!doc.closed_on || datePlusDays(doc.date_admission, 29) < doc.closed_on)
        });
    }


}
