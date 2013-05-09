function(doc) {
    //!code util/hsph.js
    
    if (!((isNewHSPHBirthCase(doc) && doc.last_status !== "lost_to_follow_up") || 
          (isHSPHBirthRegForm(doc) && doc.form.create_case === "no")))
    {
        return;
    }

    function babyXSum(property, value, n) {
        n = n || 3;
        var s = 0;
        for (var i = 1; i <= n; i++) {
            s += (doc['baby_' + i + '_' + property] === value) ? 1 : 0;
        }
        return s;
    }

    var data = {};
    
    data.birthEvents = 1;
    data.referredInBirths = 0;
    data.lostToFollowUp = 0;

    if (doc.form) {
        doc = doc.form;
    } else if (doc.last_status === 'lost_to_follow_up') {
        data.lostToFollowUp = 1;
    } else {
        data.referredInBirths = (doc.referred_in === 'yes') ? 1 : 0;

        data.maternalDeaths = (doc.maternal_death === 'yes');

        data.liveBirths = babyXSum('death', 'no');
        data.stillBirths = babyXSum('death', 'na');
        data.neonatalMortalityEvents = babyXSum('death', 'yes');

        data.maternalDeaths7Days = (doc.maternal_death_7_days === 'yes');
        data.maternalNearMisses7Days = (doc.maternal_near_miss_7_days === 'yes');
        data.stillBirths7Days = babyXSum('death_7_days', 'na');
        data.neonatalMortalityEvents7Days = babyXSum('death_7_days', 'yes');

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

    var key1 = ["region", doc.region_id, doc.district_id, doc.site_number, doc.date_admission];
    var key2 = ["site", doc.site_id, doc.date_admission];

    emit([doc.domain].concat(key1), data);
    emit([doc.domain].concat(key2), data);

    if (data.referredInBirths) {
        emit([doc.domain, "referred_in"].concat(key1), data);
        emit([doc.domain, "referred_in"].concat(key2), data);
    }
}
