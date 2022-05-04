hqDefine('registration/js/password', [
    'jquery',
    'knockout',
    'zxcvbn/dist/zxcvbn',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/knockout_bindings.ko', // password initializeValue binding
], function (
    $,
    ko,
    zxcvbn,
    initialPageData
) {
    'use strict';

    var passwordModel = function () {
        var self = {};
        self.minimumZxcvbnScore = initialPageData.get('minimumZxcvbnScore');
        self.penalizedWords = ['dimagi', 'commcare', 'hq', 'commcarehq'];
        self.password = ko.observable();
        self.strength = ko.computed(function () {
            if (self.password()) {
                return zxcvbn(self.password(), self.penalizedWords).score;
            }
            return 0;
        });
        var suggestionClick = 0;
        $(document).ready(function () {
            $("#help_text").trigger('click');
            suggestionClick += 1;
        });

        self.isSuggestedPassword = ko.observable(false);
        self.firstSuggestion = function () {
            if (suggestionClick < 1) {
                self.isSuggestedPassword(true);
            }
        };
        self.password.subscribe(function () {
            self.isSuggestedPassword(false);
        });
        self.color = ko.computed(function () {
            if (self.strength() < self.minimumZxcvbnScore - 1) {
                return "text-error text-danger";
            } else if (self.strength() < self.minimumZxcvbnScore || self.isSuggestedPassword()) {
                return "text-warning";
            } else {
                return "text-success";
            }
        });
        self.passwordHelp = ko.computed(function () {
            if (!self.password()) {
                return '';
            } else if (self.strength() >= self.minimumZxcvbnScore && self.isSuggestedPassword()) {
                return gettext("<i class='fa fa-warning'></i>" +
                    "This password is automatically generated. " +
                    "Please copy it or create your own. It will not be shown again.");
            } else if (self.strength() < self.minimumZxcvbnScore - 1) {
                return gettext("Your password is too weak! Try adding numbers or symbols!");
            } else if (self.strength() < self.minimumZxcvbnScore) {
                return gettext("Your password is almost strong enough! Try adding numbers or symbols!");
            } else {
                return gettext("Good Job! Your password is strong!");
            }
        });
        self.passwordSufficient = ko.computed(function () {
            return self.strength() >= self.minimumZxcvbnScore;
        });
        self.submitCheck = function (formElement) {
            if (self.passwordSufficient()) {
                return true;
            }
        };
        return self;
    };

    var $checkPassword = $('.check-password');
    if ($checkPassword.length && !initialPageData.get('hide_password_feedback')) {
        $checkPassword.koApplyBindings(passwordModel());
    }
});
