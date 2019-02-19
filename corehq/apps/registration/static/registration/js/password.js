(function () {
    var passwordModel = function () {
        var self = {};
        self.penalizedWords = ['dimagi', 'commcare', 'hq', 'commcarehq'];
        self.password = ko.observable();
        self.strength = ko.computed(function () {
            if (self.password()) {
                return zxcvbn(self.password(), self.penalizedWords).score;
            }
            return 0;
        });
        self.color = ko.computed(function () {
            if (self.strength() < 1) {
                return "text-error text-danger";
            } else if (self.strength() == 1) {
                return "text-warning";
            } else {
                return "text-success";
            }
        });
        self.passwordHelp = ko.computed(function () {
            if (!self.password()) {
                return '';
            } else if (self.strength() < 1) {
                return gettext("Your password is too weak! Try adding numbers or symbols!");
            } else if (self.strength() === 1) {
                return gettext("Your password is almost strong enough! Try adding numbers or symbols!");
            } else {
                return gettext("Good Job! Your password is strong!");
            }
        });
        self.passwordSufficient = ko.computed(function () {
            return self.strength() > 1;
        });
        return self;
    };

    var $checkPassword = $('.check-password');
    if ($checkPassword.length) {
        $checkPassword.koApplyBindings(passwordModel());
    }
})();
