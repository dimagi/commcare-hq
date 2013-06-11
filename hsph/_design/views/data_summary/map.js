function(doc) {
    //!code util/hsph.js
    
    if (!((isNewHSPHBirthCase(doc) && doc.last_status !== "lost_to_follow_up") || 
          (isHSPHBirthRegForm(doc) && doc.form.create_case === "no")))
    {
        return;
    }

    function babyXSum(doc, property, value, n) {
        n = n || 3;
        var s = 0;
        for (var i = 1; i <= n; i++) {
            s += (doc['baby_' + i + '_' + property] === value) ? 1 : 0;
        }
        return s;
    }

    var data = {},
        case_or_form,
        date_admission;
    
    data.birthEvents = 1;
    data.referredInBirths = 0;
    data.lostToFollowUp = 0;

    if (doc.form) {
        case_or_form = doc.form;
        date_admission = doc.form.date_admission;
    } else if (doc.last_status === 'lost_to_follow_up') {
        case_or_form = doc;
        data.lostToFollowUp = 1;
        date_admission = doc.form.date_admission;
    } else {
        case_or_form = doc;
        date_admission = doc.date_admission;
        data.referredInBirths = (doc.referred_in === 'yes') ? 1 : 0;

        data.maternalDeaths = (doc.maternal_death === 'yes');

        data.liveBirths = babyXSum(doc, 'death', 'no');
        data.stillBirths = babyXSum(doc, 'death', 'na');
        data.neonatalMortalityEvents = babyXSum(doc, 'death', 'yes');

        data.maternalDeaths7Days = (doc.maternal_death_7_days === 'yes');
        data.maternalNearMisses7Days = (doc.maternal_near_miss_7_days === 'yes');
        data.stillBirths7Days = babyXSum(doc, 'death_7_days', 'na');
        data.neonatalMortalityEvents7Days = babyXSum(doc, 'death_7_days', 'yes');

        data.totalMaternalDeaths = (data.maternalDeaths || data.maternalDeaths7Days);
        data.totalMaternalNearMisses = data.maternalNearMisses7Days;

        data.totalStillBirths = Math.max(data.stillBirths, data.stillBirths7Days);
        data.totalNeonatalMortalityEvents = Math.max(data.neonatalMortalityEvents, 
                                               data.neonatalMortalityEvents7Days);

        data.positiveOutcome = (data.totalMaternalDeaths || data.totalStillBirth || 
            data.totalMaternalNearMisses || data.totalNeonatalMortalityEvents);
        data.negativeOutcome = !data.primaryOutcomeYes;

        data.combinedMortalityOutcomes = (
            data.totalMaternalDeaths + data.totalStillBirths +
            data.totalNeonatalMortalityEvents);
        
        data.cSections = (doc.type_delivery === 'c_section');
        data.referredOut = (doc.mother_delivered_or_referred === 'referred');
    }

    data.followedUp = !data.lostToFollowUp;

    var cof = case_or_form,
        key1 = ["region", cof.region_id, cof.district_id, cof.site_number, date_admission],
        key2 = ["site", cof.site_id, date_admission];

    emit([doc.domain].concat(key1), data);
    emit([doc.domain].concat(key2), data);

    if (data.referredInBirths) {
        emit([doc.domain, "referred_in"].concat(key1), data);
        emit([doc.domain, "referred_in"].concat(key2), data);
    }
}
