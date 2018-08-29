/* This is used as the main module for a couple of different password-centric pages */
hqDefine("registration/js/password", [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'zxcvbn/dist/zxcvbn',
    'registration/js/login',
    'nic_compliance/js/encoder',
], function (
    $,
    ko,
    initialPageData,
    zxcvbn
) {
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

    $(function() {
        // Password feedback
        if (!(initialPageData.get("hide_password_feedback"))) {
            var $checkPassword = $('.check-password');
            if ($checkPassword.length) {
                $checkPassword.koApplyBindings(passwordModel());
            }
        }

        // Captcha, if present
        // http://stackoverflow.com/a/20371801
        $('img.captcha').after(
            $('<span> <button class="captcha-refresh">' +
              '<i class="fa fa-refresh icon icon-refresh"></i></button></span>')
        );
        $('.captcha-refresh').click(function(){
            var $form = $(this).parent().closest('form');
            $.getJSON("/captcha/refresh/", {}, function(json) {
                $form.find('input[name$="captcha_0"]').val(json.key);
                $form.find('img.captcha').attr('src', json.image_url);
            });
            return false;
        });
    });
});
