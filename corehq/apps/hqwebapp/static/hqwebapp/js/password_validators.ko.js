
import ko from "knockout";
import zxcvbn from "zxcvbn/dist/zxcvbn";
import "knockout-validation/dist/knockout.validation.min";  // needed for ko.validation

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

