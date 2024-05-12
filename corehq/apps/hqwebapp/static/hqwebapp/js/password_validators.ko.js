'use strict';
hqDefine('hqwebapp/js/password_validators.ko', [
    'knockout',
    'zxcvbn/dist/zxcvbn',
    'knockout-validation/dist/knockout.validation.min', // needed for ko.validation
], function (
    ko,
    zxcvbn
) {
    ko.validation.rules['zxcvbnPassword'] = {
        validator: function (val, minScore, penalizedWords) {
            if (val === undefined || val.length === 0) {
                return true;  // do separate validation for required
            }
            penalizedWords = penalizedWords || ['dimagi', 'commcare', 'hq', 'commcarehq'];
            var score = zxcvbn(val, penalizedWords).score;
            return score >= minScore;
        },
        message: gettext("Your password is too weak! Try adding numbers or symbols."),
    };

    ko.validation.rules['minimumPasswordLength'] = {
        validator: function (val, minLength) {
            if (val === undefined || val.length === 0) {return true;}  // do separate validation for required
            return val.length >= minLength;
        },
    };

    ko.validation.registerExtenders();

});
