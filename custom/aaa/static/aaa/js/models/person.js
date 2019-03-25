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
        self.gender = data.gender;
        self.status = data.status;
        self.dob = data.dob;
        self.marriedAt = data.marriedAt;
        self.aadhaarNo = data.aadhaarNo;

        self.address = data.address;
        self.subcentre = data.subcentre;
        self.village = data.village;
        self.anganwadiCentre = data.anganwadiCentre;
        self.phone = data.phone;
        self.religion = data.religion;
        self.caste = data.caste;
        self.bplOrApl = data.bplOrApl;

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
