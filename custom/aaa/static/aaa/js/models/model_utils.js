hqDefine("aaa/js/models/model_utils", [
    'jquery',
    'knockout',
    'underscore',
], function (
    $,
    ko,
    _
) {

    var pncModel = function (options) {
        var self = {};

        self.pncDate = ko.observable(options.pncDate);

        // pregnant women pnc visit
        self.postpartumHeamorrhage = ko.observable(options.postpartumHeamorrhage);
        self.fever = ko.observable(options.fever);
        self.convulsions = ko.observable(options.convulsions);
        self.abdominalPain = ko.observable(options.abdominalPain);
        self.painfulUrination = ko.observable(options.painfulUrination);
        self.congestedBreasts = ko.observable(options.congestedBreasts);
        self.painfulNipples = ko.observable(options.painfulNipples);
        self.otherBreastsIssues = ko.observable(options.otherBreastsIssues);
        self.managingBreastProblems = ko.observable(options.managingBreastProblems);
        self.increasingFoodIntake = ko.observable(options.increasingFoodIntake);
        self.possibleMaternalComplications = ko.observable(options.possibleMaternalComplications);
        self.beneficiaryStartedEating = ko.observable(options.beneficiaryStartedEating);

        // child pnc visit
        self.breastfeeding = ko.observable(options.breastfeeding);
        self.skinToSkinContact = ko.observable(options.skinToSkinContact);
        self.wrappedUpAdequately = ko.observable(options.wrappedUpAdequately);
        self.awakeActive = ko.observable(options.awakeActive);

        self.pncDate = ko.computed(function () {
            if (self.pncDate() === void(0)) {
                return 'Not Done';
            }
            return self.pncDate;
        });

        self.marked = function (value) {
            if (value === void(0)) {
                return 'fa fa-minus black';
            } else if (value === 0) {
                return 'fa fa-times red';
            } else {
                return 'fa fa-check green';
            }
        };

        _.each(self, function (value, key) {
            if (key !== 'pncDate' && key !== 'marked') {
                self[key] = ko.computed(function () {
                    return self.marked(value());
                });
            }
        });

        return self;
    };

    var ancModel = function (options) {
        var self = {};

        self.ancDate = ko.observable(options.ancDate || '-');
        self.ancLocation = ko.observable(options.ancLocation || '-');
        self.pwWeight = ko.observable(options.pwWeight || '-');
        self.bloodPressure = ko.observable(options.bloodPressure || '-');
        self.hb = ko.observable(options.hb || '-');
        self.abdominalExamination = ko.observable(options.abdominalExamination || '-');
        self.abnormalitiesDetected = ko.observable(options.abnormalitiesDetected || '-');

        self.ancDate = ko.computed(function () {
            if (self.ancDate() === void(0)) {
                return 'Not Done';
            }
            return self.ancDate;
        });

        return self;
    };

    var vaccinationModel = function (options) {
        var self = {};

        self.vitaminName = ko.observable(options.vitaminName);
        self.date = ko.observable(options.date);
        self.adverseEffects = ko.observable(options.adverseEffects);

        return self;
    };

    return {
        pncModel: pncModel,
        ancModel: ancModel,
        vaccinationModel: vaccinationModel,
    };
});
