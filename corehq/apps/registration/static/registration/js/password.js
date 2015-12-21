(function () {
    var PasswordModel = function () {
        var self = this;
        self.penalizedWords = ['dimagi', 'commcare', 'hq', 'commcarehq'];
        self.password = ko.observable('');
        self.strength = ko.computed(function () {
            return zxcvbn(self.password(), self.penalizedWords).score;
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
            } else if (self.strength() == 1) {
                return gettext("Your password is almost strong enough!");
            } else {
                return gettext("Good Job! Your password is strong!");
            }
        });
    };

    var passwordModel = new PasswordModel();
    $('fieldset').koApplyBindings(passwordModel);
})();
