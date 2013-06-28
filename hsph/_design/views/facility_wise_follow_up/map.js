
function(doc){
    // !code util/hsph.js

    form = doc.form ? doc.form : doc;

    if (isNewHSPHBirthCase(form)) {
        var regionId = form.region_id;
        var districtId = form.district_id;
        var siteId = form.site_id;
        var siteNumber = form.site_number;
        var siteName = form.site_name;

        var entry = new HSPHEntry(form);
        entry.getSiteInfo();
        entry.getCaseInfo();
        entry.getBirthStats();
        
        var numOfBirths = entry.data.numBirths;
        if (numOfBirths) {
            emit([regionId, districtId, siteNumber, siteId, doc.user_id,
                'births', , form.date_admission.substring(0, 10)], numOfBirths);
        }
         
        if (entry.data.isClosed && form.last_status === 'followed_up') {
            emit([regionId, districtId, siteNumber, siteId, doc.user_id,
                'closed_cases', form.date_admission.substring(0, 10)], 1);
        }
        
        if (entry.data.isClosed && form.last_status === 'lost_to_follow_up') {
            emit([regionId, districtId, siteNumber, siteId, doc.user_id,
                'lost_to_follow_up', form.date_admission.substring(0, 10)], 1);
        }
         
        if (entry.data.isClosed && (form.closed_by === 'cati_tl' ||
                form.closed_by === 'cati')) 
        {
            emit([regionId, districtId, siteNumber, siteId, doc.user_id,
             'followed_up_by_call_center', form.date_admission.substring(0, 10)], 1);
        }
        
        if (entry.data.isClosed && form.closed_by === 'fida'){
            emit([regionId, districtId, siteNumber, siteId, doc.user_id,
                'followed_up_by_field', form.date_admission.substring(0, 10) ], 1);
        }
     
        if((!entry.data.isClosed) && form.date_admission){
            emit([regionId, districtId, siteNumber, siteId, doc.user_id,
                'needing_follow_up', form.date_admission.substring(0, 10),
                form.date_admission.substring(0, 10)], 1);
        }

        if(!entry.data.isClosed ){
            emit([regionId, districtId, siteNumber, siteId, doc.user_id,
                'open_cases', form.date_admission.substring(0, 10)], 1);
        }       
    }
}

