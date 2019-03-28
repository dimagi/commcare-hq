describe('Model Utils', function () {
    var utilsModels;

    beforeEach(function () {
        utilsModels = hqImport('aaa/js/models/model_utils');
    });

    describe('pnc model', function () {
        it('test model properties', function () {
            var pncModel = utilsModels.pncModel({});
            assert.isTrue(pncModel.hasOwnProperty('pncDate'));
            assert.isTrue(pncModel.hasOwnProperty('postpartumHeamorrhage'));
            assert.isTrue(pncModel.hasOwnProperty('fever'));
            assert.isTrue(pncModel.hasOwnProperty('convulsions'));
            assert.isTrue(pncModel.hasOwnProperty('abdominalPain'));
            assert.isTrue(pncModel.hasOwnProperty('painfulUrination'));
            assert.isTrue(pncModel.hasOwnProperty('congestedBreasts'));
            assert.isTrue(pncModel.hasOwnProperty('painfulNipples'));
            assert.isTrue(pncModel.hasOwnProperty('otherBreastsIssues'));
            assert.isTrue(pncModel.hasOwnProperty('managingBreastProblems'));
            assert.isTrue(pncModel.hasOwnProperty('increasingFoodIntake'));
            assert.isTrue(pncModel.hasOwnProperty('possibleMaternalComplications'));
            assert.isTrue(pncModel.hasOwnProperty('beneficiaryStartedEating'));
            assert.isTrue(pncModel.hasOwnProperty('breastfeeding'));
            assert.isTrue(pncModel.hasOwnProperty('skinToSkinContact'));
            assert.isTrue(pncModel.hasOwnProperty('wrappedUpAdequately'));
            assert.isTrue(pncModel.hasOwnProperty('awakeActive'));
        });
    });

    describe('anc model', function () {
        it('test model properties', function () {
            var ancModel = utilsModels.ancModel({});
            assert.isTrue(ancModel.hasOwnProperty('ancDate'));
            assert.isTrue(ancModel.hasOwnProperty('ancLocation'));
            assert.isTrue(ancModel.hasOwnProperty('pwWeight'));
            assert.isTrue(ancModel.hasOwnProperty('bloodPressure'));
            assert.isTrue(ancModel.hasOwnProperty('hb'));
            assert.isTrue(ancModel.hasOwnProperty('abdominalExamination'));
            assert.isTrue(ancModel.hasOwnProperty('abnormalitiesDetected'));
        });
    });

    describe('vaccination model', function () {
        it('test model properties', function () {
            var vaccinationModel = utilsModels.vaccinationModel({});
            assert.isTrue(vaccinationModel.hasOwnProperty('vitaminName'));
            assert.isTrue(vaccinationModel.hasOwnProperty('date'));
            assert.isTrue(vaccinationModel.hasOwnProperty('adverseEffects'));
        });
    });
});
