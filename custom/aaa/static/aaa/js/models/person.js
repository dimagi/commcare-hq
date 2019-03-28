hqDefine("aaa/js/models/person", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    ko,
    _,
    initialPageData,
) {
    var personModel = function (data, postData) {
        var self = {};
        self.id = data.id;
        self.name = data.name;
        self.gender = data.sex;
        self.status = data.migration_status;
        self.dob = data.dob;
        self.marriedAt = data.age_marriage;
        self.aadhaarNo = data.has_aadhar_number;

        self.address = data.hh_address;
        self.subcentre = data.sc;
        self.village = data.village;
        self.anganwadiCentre = data.awc;
        self.phone = data.contact_phone_number;
        self.religion = data.hh_religion;
        self.caste = data.hh_caste;
        self.bplOrApl = data.hh_bpl_apl;

        self.age = ko.computed(function () {
            var age = Math.floor(moment(new Date()).diff(moment(self.dob, "YYYY-MM-DD"),'months',true));
            if (age < 12) {
                return age + " Mon";
            } else if (age % 12 === 0) {
                return Math.floor(age / 12) + " Yr";
            } else {
                return Math.floor(age / 12) + " Yr " + age % 12 + " Mon";
            }
        });

        self.gender = ko.computed(function () {
            return self.gender === 'M' ? 'Male' : 'Female';
        });

        self.aadhaarNo = ko.computed(function () {
            return self.aadhaarNo ? 'Yes' : 'No';
        });

        self.nameLink = ko.computed(function () {
            var url = initialPageData.reverse('unified_beneficiary_details');
            url = url.replace('details_type', 'eligible_couple');
            url = url.replace('beneficiary_id', 1);
            url = url + '?month=' + postData.selectedMonth() + '&year=' + postData.selectedYear();
            return '<a href="' + url + '">' + self.name + '</a>';
        });

        return self;
    };

    return {
        personModel: personModel,
    }
});
