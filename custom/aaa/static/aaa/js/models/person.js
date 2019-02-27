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
    var personModel = function (data) {
        var self = {};
        self.name = data.name;
        self.gender = data.gender;
        self.status = data.status;
        self.dob = data.dob;
        self.marriedAt = data.marriedAt;
        self.aadhaarNo = data.aadhaarNo;

        self.age = ko.computed(function () {
            return Math.floor(moment(new Date()).diff(moment(self.dob, "YYYY-MM-DD"),'years',true)) + ' Yrs';
        });
        return self;
    };

    var personOtherInfoModel = function (data) {
        var self = {};
        self.address = data.address;
        self.subcentre = data.subcentre;
        self.village = data.village;
        self.anganwadiCentre = data.anganwadiCentre;
        self.phone = data.phone;
        self.religion = data.religion;
        self.caste = data.caste;
        self.bplOrApl = data.bplOrApl;
        return self;
    };

    return {
        personModel: personModel,
        personOtherInfoModel: personOtherInfoModel,
    }
});
