function(doc) {
    //!code util/hsph.js

    if (isCATIFollowUpForm(doc)) {
        var data = {},
            form = doc.form,
            followUpTime = get_form_filled_duration(doc),
            submissionDay = get_submission_day(doc), 
            key = [form.meta.userID, form.date_admission];

        data.waitlisted = (form.last_status === 'cati_waitlist');
        data.transferredToTeamLeader = (form.last_status === 'cati_tl');
        
        if (followUpTime) {
            data.followUpTime = followUpTime;
        }
        if (submissionDay) {
            emit(["submission_day"].concat(key), submissionDay);
        }

        emit(key, data); 
        return;
    }

    if (!isHSPHBirthCase(doc)) {
        return;
    }
        
    function datePlusDays(string, daysToAdd) {
        var newDate = new Date(string);
        newDate.setDate(newDate.getDate() + daysToAdd);
        return newDate;
    }

    // get first and last follow up time from case actions
    
    var firstFollowUpTime = false,
        lastFollowUpTime = false;

    for (var i in doc.actions) {
        var action = doc.actions[i],
            properties = action.updated_unknown_properties;
        for (var prop in action.updated_known_properties) {
            properties[prop] = action.updated_known_properties[prop];
        }

        if (typeof properties.follow_up_type !== 'undefined') {
            var time = (new Date(action.date)).getTime();
            
            if (!firstFollowUpTime) {
                firstFollowUpTime = time;
            }

            if (!lastFollowUpTime || time > lastFollowUpTime) {
                lastFollowUpTime = time;
            }
        }
    }

    // calculate indicators

    var data = {},
        openedOn = datePlusDays(doc.opened_on, 0).getTime(),
        admissionDatePlus13 = datePlusDays(doc.date_admission, 11).getTime(),
        admissionDatePlus21 = datePlusDays(doc.date_admission, 13).getTime();

    data.followedUp = (doc.follow_up_type === 'followed_up');

    data.noFollowUpAfter6Days = (doc.date_admission &&
        (!firstFollowUpTime || admissionDatePlus13 < firstFollowUpTime));
    
    data.catiTimedOut = (doc.date_admission && 
        (!(doc.closed_on) || admissionDatePlus21 < lastFollowUpTime));

    emit([doc.user_id, doc.date_admission], data);
}
