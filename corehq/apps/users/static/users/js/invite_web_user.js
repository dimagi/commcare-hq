hqDefine('users/js/invite_web_user',[
    'jquery',
    'knockout',
    'hqwebapp/js/validators.ko',
], function (
    $,
    ko
) {
    'use strict';

    var inviteWebUserFormHandler = function () {
        var self = {};

        self.email = ko.observable()
            .extend({
                required: {
                    message: django.gettext("Please specify an email."),
                    params: true,
                },
                emailRFC2822: true,
            });

        return self;
    };

    $(function () {
        var formHandler = inviteWebUserFormHandler();
        $('#invite-web-user-form').koApplyBindings(formHandler);
    });
});
