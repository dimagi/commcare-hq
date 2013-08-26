function(doc) {
    //!code util/hsph.js
    
    if (isCATIFollowUpForm(doc)) {
        var data = {},
            form = doc.form,
            followUpTime = get_form_filled_seconds(doc),
            submissionDay = get_submission_day(doc),
            userID = form.meta.userID,
            date = form.date_admission;
        
        data.waitlisted = (form.last_status === 'cati_waitlist') ? 1 : 0;
        data.transferredToTeamLeader = (form.last_status === 'cati_tl') ? 1 : 0;
       
        data.followUpForms = 1;
        if (followUpTime) {
            data.followUpTime = followUpTime;
        }

        if (submissionDay) {
            emit(["submissionDay", doc.domain, userID, date], {
                submissionDay: submissionDay
            });
        }

        emit(["followUpForm", doc.domain, userID, date], data);
        return;
    }

    if (isNewHSPHBirthCase(doc)) {
        var data = {},
            date = doc.date_admission;

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
        var admissionDatePlus13 = datePlusDays(doc.date_admission, 13).getTime(),
            admissionDatePlus21 = datePlusDays(doc.date_admission, 21).getTime();

        data.followedUp = (doc.last_status === 'followed_up') ? 1 : 0;

        emit(["noFollowUpAfter6Days", doc.domain, doc.owner_id, date], {
            noFollowUpAfter6Days: (doc.date_admission &&
            (!firstFollowUpTime || admissionDatePlus13 < firstFollowUpTime)) ? 1 : 0
        });
        
        emit(["timedOut", doc.domain, doc.owner_id, date], {
            timedOut: (doc.date_admission && 
            (!(doc.closed_on) || admissionDatePlus21 < lastFollowUpTime)) ? 1 : 0
        });
        
        emit(["all", doc.domain, doc.owner_id, date], data);
    }
}
