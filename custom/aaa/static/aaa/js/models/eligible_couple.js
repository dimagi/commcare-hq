hqDefine("aaa/js/models/eligible_couple", [
    'jquery',
    'knockout',
    'underscore',
    'moment/moment',
    'hqwebapp/js/initial_page_data',
    'aaa/js/models/child',
    'aaa/js/models/person',
], function (
    $,
    ko,
    _,
    moment,
    initialPageData,
    childUtils,
    personUtils
) {
    var eligibleCoupleList = function (options, postData) {
        var self = {};
        self.id = options.id;
        self.name = ko.observable(options.name);
        self.dob = ko.observable(options.dob);
        self.adoptionDateOfFamilyPlaning = ko.observable(options.adoptionDateOfFamilyPlaning);

        self.age = ko.computed(function () {
            if (self.dob() === 'N/A') {
                return self.dob();
            }
            var age = Math.floor(moment(postData.selectedDate()).diff(
                moment(self.dob(), "YYYY-MM-DD"),'months',true)
            );
            if (age < 12) {
                return age + " Mon";
            } else if (age % 12 === 0) {
                return Math.floor(age / 12) + " Yr";
            } else {
                return Math.floor(age / 12) + " Yr " + age % 12 + " Mon";
            }
        });

        self.currentFamilyPlanningMethod = ko.computed(function () {
            return options.currentFamilyPlanningMethod !== null ? options.currentFamilyPlanningMethod : 'N/A';
        });

        self.adoptionDateOfFamilyPlaning = ko.computed(function () {
            return options.adoptionDateOfFamilyPlaning !== null ? options.adoptionDateOfFamilyPlaning : 'N/A';
        });

        self.name = ko.computed(function () {
            var url = initialPageData.reverse('unified_beneficiary_details');
            url = url.replace('details_type', 'eligible_couple');
            url = url.replace('beneficiary_id', self.id);
            url = url + '?month=' + postData.selectedMonth() + '&year=' + postData.selectedYear();
            return '<a href="' + url + '">' + self.name() + '</a>';
        });

        return self;
    };

    var eligibleCoupleListConfig = function () {
        var self = {};
        self.columns = [
            {data: 'name()', name: 'name', title: 'Name'},
            {data: 'age()', name: 'dob', title: 'Age'},
            {data: 'currentFamilyPlanningMethod()', name: 'currentFamilyPlanningMethod', title: 'Current Family Planning Method'},
            {data: 'adoptionDateOfFamilyPlaning()', name: 'adoptionDateOfFamilyPlaning', title: 'Adoption Date Of Family Planing'},
        ];
        return self;
    };

    var eligibleCoupleModel = function (data) {
        var self = {};
        self.maleChildrenBorn = data.maleChildrenBorn;
        self.femaleChildrenBorn = data.femaleChildrenBorn;
        self.maleChildrenAlive = data.maleChildrenAlive;
        self.femaleChildrenAlive = data.femaleChildrenAlive;
        self.familyPlaningMethod = data.familyPlaningMethod;
        self.familyPlanningMethodDate = data.familyPlanningMethodDate;
        self.ashaVisit = data.ashaVisit;
        self.previousFamilyPlanningMethod = data.previousFamilyPlanningMethod;
        self.preferredFamilyPlaningMethod = data.preferredFamilyPlaningMethod;

        self.childrenBorn = ko.computed(function () {
            return self.maleChildrenBorn + ' (Male), ' + self.femaleChildrenBorn + ' (Female)';
        });

        self.childrenAlive = ko.computed(function () {
            return self.maleChildrenAlive + ' (Male), ' + self.femaleChildrenAlive + ' (Female)';
        });

        return self;
    };
    
    var eligibleCoupleDetailsView = function (postData) {
        var self = {};
        self.personDetails = {
            person: ko.observable(personUtils.personModel),
            husband: ko.observable(personUtils.personModel),
        };
        self.childDetails = ko.observableArray([]);
        self.eligibleCoupleDetails = ko.observable(eligibleCoupleModel);
        self.postData = postData;

        self.sections = [
            'person_details',
            'children_list',
            'eligible_couple_details',
        ];


        self.getPersonDetails = function () {
            var params = Object.assign({
                section: 'eligible_couple',
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
                section: 'eligible_couple',
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

        self.getEligibleCoupleDetails = function () {
            var params = Object.assign({
                section: 'eligible_couple',
                subsection: 'eligible_couple_details',
                beneficiaryId: initialPageData.get('beneficiary_id'),
            }, self.postData);
            $.post(initialPageData.reverse('unified_beneficiary_details_api'), params, function (data) {
                self.eligibleCoupleDetails(eligibleCoupleModel(data));
            });
        };

        self.callback = function () {
            self.getPersonDetails();
            self.getChildDetails();
            self.getEligibleCoupleDetails();
        };

        return self;
    };

    return {
        config: eligibleCoupleListConfig,
        listView: eligibleCoupleList,
        detailsView: eligibleCoupleDetailsView,
        eligibleCoupleModel: eligibleCoupleModel,
    };
});
