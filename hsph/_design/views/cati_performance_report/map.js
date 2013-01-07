function(doc) {
    //!code views/lib/emit_array.js
    //!code util/hsph.js

    if (!isHSPHBirthCase(doc)) {
        return;
    }
        
    function datePlusDays(string, daysToAdd) {
        var newDate = new Date(string);
        newDate.setDate(newDate.getDate() + daysToAdd);
        return newDate;
    }

    function differenceInDays(time1, time2) {
        return Math.floor((time1 - time2) / (24 * 3600 * 1000));
    }

    function daysSinceEpoch(date) {
        return Math.floor(date.getTime() / (24 * 3600 * 1000));
    }

    function hasPhoneNumber(doc) {
        return (doc.phone_mother_number || doc.phone_husband_number || 
                doc.phone_asha_number || doc.phone_house_number);
    }

    // get last follow up time from case actions
    
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
        filterDatePlus11 = datePlusDays(doc.filter_date, 11).getTime(),
        filterDatePlus13 = datePlusDays(doc.filter_date, 13).getTime();

    data.followedUp = (doc.follow_up_type === 'followed_up');

    data.noFollowUpAfter4Days = !!(hasPhoneNumber(doc) &&
        (!firstFollowUpTime || filterDatePlus11 < firstFollowUpTime) &&
        doc.filter_date
    );
    
    data.transferredToManager = (doc.follow_up_type === 'direct_to_call_center_manager');

    data.transferredToField = (doc.follow_up_type === 'field_follow_up');

    data.notClosedOrTransferredAfter13Days = !!(hasPhoneNumber(doc) &&
        !(doc.closed_on || data.transferredToManager || data.transferredToField) &&
        doc.filter_date
    );

    data.workingDays = [];
    for (var i in doc.actions) {
        var days = daysSinceEpoch(new Date(doc.actions[i].date));
        if (data.workingDays.indexOf(days) === -1) {
            data.workingDays.push();
        }
    }

    data.followUpTime = lastFollowUpTime ? 
        differenceInDays(lastFollowUpTime, openedOn) : null;


    emit_array([doc.user_id], [doc.opened_on], data, {
        noFollowUpAfter4Days: [doc.filter_date || 0],
        notClosedOrTransferredAfter13Days: [doc.filter_date || 0]
    });
}
