hqDefine("aaa/js/models/pregnant_women", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'aaa/js/models/child',
    'aaa/js/models/person',
    'aaa/js/models/model_utils',
], function (
    $,
    ko,
    _,
    initialPageData,
    childUtils,
    personUtils,
    modelUtils,
) {
    var pregnantWomenList = function (options, postData) {
        var self = {};
        self.id = options.id;
        self.name = ko.observable(options.name);
        self.age = ko.observable(options.age);
        self.pregMonth = ko.observable(options.pregMonth);
        self.highRiskPregnancy = ko.observable(options.highRiskPregnancy);
        self.noOfAncCheckUps = ko.observable(options.noOfAncCheckUps);


        self.name = ko.computed(function () {
            var url = initialPageData.reverse('unified_beneficiary_details');
            url = url.replace('details_type', 'pregnant_women');
            url = url.replace('beneficiary_id', self.id);
            url = url + '?month=' + postData.selectedMonth() + '&year=' + postData.selectedYear();
            return '<a href="' + url + '">' + self.name() + '</a>';
        });

        self.highRiskPregnancy = ko.computed(function () {
            return self.highRiskPregnancy === 1 ? 'Yes': 'No';
        });
        return self;
    };

    var pregnantWomenListConfig = function () {
        var self = {};
        self.columns = [
            {data: 'name()', name: 'name', title: 'Name'},
            {data: 'age()', name: 'age', title: 'Age'},
            {data: 'pregMonth()', name: 'pregMonth', title: 'Preg. Month'},
            {data: 'highRiskPregnancy()', name: 'highRiskPregnancy', title: 'High Risk Pregnancy'},
            {data: 'noOfAncCheckUps()', name: 'noOfAncCheckUps', title: 'No. Of ANC Check-Ups'},
        ];
        return self;
    };

    var pregnantWomenDetails = function (options) {
        var self = {};
        // pregnancy_details
        self.dateOfLmp = ko.observable();
        self.weightOfPw = ko.observable();
        self.dateOfRegistration = ko.observable();
        self.edd = ko.observable();
        self.twelveWeeksPregnancyRegistration = ko.observable();
        self.bloodGroup = ko.observable();
        self.pregnancyStatus = ko.observable();
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
            _.each(data, function(value, key) {
                self[key](value);
            })
        };

        self.updatePncVisits = function (data) {
            _.each(data, function (visit) {
                self.pncVisits.push(modelUtils.pncModel(visit))
            });
            while (self.pncVisits().length < 4) {
                self.pncVisits.push(modelUtils.pncModel({}))
            }
        };

        self.updateAncVisits = function (data) {
            _.each(data, function (visit) {
                self.ancVisits.push(modelUtils.ancModel(visit))
            });
            while (self.ancVisits().length < 4) {
                self.ancVisits.push(modelUtils.ancModel({}))
            }
        };

        self.pregnancyStatusClass = function(status) {
            if (status < self.pregnancyStatus()) {
                return 'previous-status'
            } else if (status === self.pregnancyStatus()) {
                return 'current-status'
            } else {
                return '';
            }
        };

        return self;
    };

    var pregnantWomenDetailsView = function (postData) {
        var self = {};
        self.personDetails = {
            person: ko.observable(personUtils.personModel),
            husband: ko.observable(personUtils.personModel),
            other: ko.observable(personUtils.personOtherInfoModel),
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
                self.personDetails.other(personUtils.personOtherInfoModel(data.other));
            })
        };

        self.getChildDetails = function () {
            var params = Object.assign({
                subsection: 'child_details',
                beneficiaryId: initialPageData.get('beneficiary_id'),
            }, self.postData);
            $.post(initialPageData.reverse('unified_beneficiary_details_api'), params, function (data) {
                _.forEach(data.children, function(child) {
                    self.childDetails.push(childUtils.childModel(child, self.postData));
                });
                while (self.childDetails().length % 4 > 0) {
                    self.childDetails.push({})
                }
            })
        };

        self.getPregnantDetails = function(subsection) {
            var params = Object.assign({
                section: 'pregnant_women',
                subsection: subsection,
                beneficiaryId: initialPageData.get('beneficiary_id'),
            }, self.postData);
            $.post(initialPageData.reverse('unified_beneficiary_details_api'), params, function (data) {
                if (subsection === 'postnatal_care_details') {
                    self.pregnantDetails().updatePncVisits(data.visits)
                } else if (subsection === 'antenatal_care_details') {
                    self.pregnantDetails().updateAncVisits(data.visits)
                } else {
                    self.pregnantDetails().updateModel(data)
                }
            })
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
        detailsView: pregnantWomenDetailsView
    }
});
