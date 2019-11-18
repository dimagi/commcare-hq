hqDefine("aaa/js/models/pregnant_women", [
    'jquery',
    'knockout',
    'underscore',
    'moment/moment',
    'hqwebapp/js/initial_page_data',
    'aaa/js/models/child',
    'aaa/js/models/person',
    'aaa/js/models/model_utils',
    'aaa/js/utils/reach_utils',
], function (
    $,
    ko,
    _,
    moment,
    initialPageData,
    childUtils,
    personUtils,
    modelUtils,
    reachUtils
) {
    var pregnantWomenList = function (options, postData) {
        var self = {};
        self.id = options.id;
        self.name = ko.observable(options.name);
        self.dob = ko.observable(options.dob);
        self.pregMonth = ko.observable(options.pregMonth);
        self.highRiskPregnancy = ko.observable(options.highRiskPregnancy);
        self.noOfAncCheckUps = ko.observable(options.noOfAncCheckUps);

        self.age = ko.computed(function () {
            if (self.dob() === 'N/A') {
                return self.dob();
            }
            var age = Math.floor(moment(postData.selectedDate()).diff(
                moment(self.dob(), "YYYY-MM-DD"),'months',true)
            );if (age < 12) {
                return age + " Mon";
            } else if (age % 12 === 0) {
                return Math.floor(age / 12) + " Yr";
            } else {
                return Math.floor(age / 12) + " Yr " + age % 12 + " Mon";
            }
        });

        self.name = ko.computed(function () {
            var url = initialPageData.reverse('unified_beneficiary_details');
            url = url.replace('details_type', 'pregnant_women');
            url = url.replace('beneficiary_id', self.id);
            url = url + '?month=' + postData.selectedMonth() + '&year=' + postData.selectedYear();
            return '<a href="' + url + '">' + self.name() + '</a>';
        });

        self.highRiskPregnancy = ko.computed(function () {
            return self.highRiskPregnancy() === 'yes' ? 'Yes' : 'No';
        });

        self.noOfAncCheckUps = ko.computed(function () {
            return self.noOfAncCheckUps() === null ? 0 : self.noOfAncCheckUps();
        });
        return self;
    };

    var pregnantWomenListConfig = function () {
        var self = {};
        self.columns = [
            {data: 'name()', name: 'name', title: 'Name'},
            {data: 'age()', name: 'dob', title: 'Age'},
            {data: 'pregMonth()', name: 'pregMonth', title: 'Preg. Month'},
            {data: 'highRiskPregnancy()', name: 'highRiskPregnancy', title: 'High Risk Pregnancy'},
            {data: 'noOfAncCheckUps()', name: 'noOfAncCheckUps', title: 'No. Of ANC Check-Ups'},
        ];
        return self;
    };

    var pregnantWomenDetails = function () {
        var self = {};
        // pregnancy_details
        self.weightOfPw = ko.observable();
        self.dateOfRegistration = ko.observable();
        self.edd = ko.observable();
        self.add = ko.observable();
        self.lmp = ko.observable();
        self.bloodGroup = ko.observable();
        // pregnancy_risk
        self.riskPregnancy = ko.observable();
        self.referralDate = ko.observable();
        self.hrpSymptoms = ko.observable();
        self.illnessHistory = ko.observable();
        self.referredOutFacilityType = ko.observable();
        self.pastIllnessDetails = ko.observable();
        // consumables_disbursed
        self.ifaTablets = ko.observable();
        self.thrDisbursed = ko.observable();
        // immunization_counseling_details
        self.ttDoseOne = ko.observable();
        self.ttDoseTwo = ko.observable();
        self.ttBooster = ko.observable();
        self.birthPreparednessVisitsByAsha = ko.observable();
        self.birthPreparednessVisitsByAww = ko.observable();
        self.counsellingOnMaternal = ko.observable();
        self.counsellingOnEbf = ko.observable();
        // abortion_details
        self.abortionDate = ko.observable();
        self.abortionType = ko.observable();
        self.abortionDays = ko.observable();
        // maternal_death_details
        self.maternalDeathOccurred = ko.observable();
        self.maternalDeathPlace = ko.observable();
        self.maternalDeathDate = ko.observable();
        self.authoritiesInformed = ko.observable();
        // delivery_details
        self.dod = ko.observable();
        self.assistanceOfDelivery = ko.observable();
        self.timeOfDelivery = ko.observable();
        self.dateOfDischarge = ko.observable();
        self.typeOfDelivery = ko.observable();
        self.timeOfDischarge = ko.observable();
        self.placeOfBirth = ko.observable();
        self.deliveryComplications = ko.observable();
        self.placeOfDelivery = ko.observable();
        self.complicationDetails = ko.observable();
        self.hospitalType = ko.observable();
        // postnatal_care_details
        self.pncVisits = ko.observableArray();
        self.ancVisits = ko.observableArray();

        self.updateModel = function (data) {
            _.each(data, function (value, key) {
                self[key](value);
            });
        };

        self.updatePncVisits = function (data) {
            _.each(data, function (visit) {
                self.pncVisits.push(modelUtils.pncModel(visit));
            });
            while (self.pncVisits().length < 4) {
                self.pncVisits.push(modelUtils.pncModel({}));
            }
        };

        self.updateAncVisits = function (data) {
            _.each(data, function (visit) {
                self.ancVisits.push(modelUtils.ancModel(visit));
            });
            while (self.ancVisits().length < 4) {
                self.ancVisits.push(modelUtils.ancModel({}));
            }
        };

        self.pregnancyStatusClass = function (status) {
            if (status < self.pregnancyStatus()) {
                return 'previous-status';
            } else if (status === self.pregnancyStatus()) {
                return 'current-status';
            } else {
                return '';
            }
        };

        self.twelveWeeksPregnancyRegistration = ko.computed(function () {
            var diffAddAndLmp = Math.floor(moment(self.add(), "YYYY-MM-DD").diff(moment(self.lmp(), "YYYY-MM-DD"),'weeks',true));
            return diffAddAndLmp < 12 ? 'Yes' : 'No';
        });

        self.pregnancyStatus = ko.computed(function () {
            // 3 - PNC
            // 2 - Due for delivery
            // 1 - Pregnancy
            var diffEddAndLmp = Math.floor(moment(self.edd(), "YYYY-MM-DD").diff(moment(self.lmp(), "YYYY-MM-DD"), 'days', true));
            var diffNowAndAdd = Math.floor(moment(new Date()).diff(moment(self.add(), "YYYY-MM-DD"), 'days', true));
            if (diffNowAndAdd <= 42) {
                return 3;
            } else if (diffEddAndLmp <= 90) {
                return 2;
            } else {
                return 1;
            }
        });

        self.personBloodGroup = ko.computed(function () {
            if (!reachUtils.BLOODGROUPS.hasOwnProperty(self.bloodGroup())) {
                return 'N/A';
            }
            return reachUtils.BLOODGROUPS[self.bloodGroup()];
        });

        self.abortionWeeks = ko.computed(function () {
            if (self.abortionDays() !== undefined) {
                return self.abortionDays() === parseInt(self.abortionDays()) ? parseInt(self.abortionDays() / 7) : self.abortionDays();
            } else {
                return 'N/A';
            }
        });

        return self;
    };

    var pregnantWomenDetailsView = function (postData) {
        var self = {};
        self.personDetails = {
            person: ko.observable(personUtils.personModel),
            husband: ko.observable(personUtils.personModel),
        };
        self.childDetails = ko.observableArray([]);

        self.pregnantDetails = ko.observable(pregnantWomenDetails());

        self.postData = postData;

        self.sections = [
            'person_details',
            'children_list',
            'pregnancy_details',
            'pregnancy_risk',
            'antenatal_care_details',
            'consumables_disbursed',
            'immunization_counseling_details',
            'abortion_details',
            'maternal_death_details',
            'delivery_details',
            'postnatal_care_details',
        ];

        self.getPersonDetails = function () {
            var params = Object.assign({
                section: 'pregnant_women',
                subsection: 'person_details',
                beneficiaryId: initialPageData.get('beneficiary_id'),
            }, self.postData);
            $.post(initialPageData.reverse('unified_beneficiary_details_api'), params, function (data) {
                self.personDetails.person(personUtils.personModel(data.person, self.postData));
                self.personDetails.husband(personUtils.personModel(data.husband, self.postData));
            });
        };

        self.getChildDetails = function () {
            var params = Object.assign({
                subsection: 'child_details',
                beneficiaryId: initialPageData.get('beneficiary_id'),
            }, self.postData);
            $.post(initialPageData.reverse('unified_beneficiary_details_api'), params, function (data) {
                _.forEach(data.children, function (child) {
                    self.childDetails.push(childUtils.childModel(child, self.postData));
                });
                while (self.childDetails().length % 4 > 0) {
                    self.childDetails.push({});
                }
            });
        };

        self.getPregnantDetails = function (subsection) {
            var params = Object.assign({
                section: 'pregnant_women',
                subsection: subsection,
                beneficiaryId: initialPageData.get('beneficiary_id'),
            }, self.postData);
            $.post(initialPageData.reverse('unified_beneficiary_details_api'), params, function (data) {
                if (subsection === 'postnatal_care_details') {
                    self.pregnantDetails().updatePncVisits(data.visits);
                } else if (subsection === 'antenatal_care_details') {
                    self.pregnantDetails().updateAncVisits(data.visits);
                } else {
                    self.pregnantDetails().updateModel(data);
                }
            });
        };

        self.callback = function () {
            self.getPersonDetails();
            self.getChildDetails();
            self.getPregnantDetails('pregnancy_details');
            self.getPregnantDetails('pregnancy_risk');
            self.getPregnantDetails('antenatal_care_details');
            self.getPregnantDetails('consumables_disbursed');
            self.getPregnantDetails('immunization_counseling_details');
            self.getPregnantDetails('abortion_details');
            self.getPregnantDetails('maternal_death_details');
            self.getPregnantDetails('delivery_details');
            self.getPregnantDetails('postnatal_care_details');
        };

        return self;
    };

    return {
        config: pregnantWomenListConfig,
        listView: pregnantWomenList,
        detailsView: pregnantWomenDetailsView,
        pregnantModel: pregnantWomenDetails,
    };
});
