/* global ko */
/* global django */
/* global zxcvbn */

ko.validation.rules['zxcvbnPassword'] = {
    validator: function (val, minScore, penalizedWords) {
        if (val === undefined || val.length === 0) return true;  // do separate validation for required
        penalizedWords = penalizedWords || ['dimagi', 'commcare', 'hq', 'commcarehq'];
        var score = zxcvbn(val, penalizedWords).score;
        return score >= minScore;
    },
    message: django.gettext("Your password is too weak! Try adding numbers or symbols."),
};

ko.validation.registerExtenders();
