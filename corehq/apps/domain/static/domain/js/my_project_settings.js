hqDefine("domain/js/my_project_settings", [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'commcarehq',
], function (
    $,
    ko,
    initialPageData
) {
    var HQTimezoneHandler = function (o) {
        var self = {};

        self.override_tz = ko.observable(o.override);
        self.no_domain_membership = ko.observable(o.no_domain_membership);
        self.disableUpdateSettings = ko.observable(true);

        self.updateForm = function () {
            self.disableUpdateSettings(self.no_domain_membership());
        };

        return self;
    };

    $(function () {
        $('#my-project-settings-form').koApplyBindings(HQTimezoneHandler({
            override: initialPageData.get('override_global_tz'),
            no_domain_membership: initialPageData.get('no_domain_membership'),
        }));

        var $globalTimezone = $('#id_global_timezone'),
            $userTimezone = $('#id_user_timezone'),
            $overrideGlobalTimezone = $('#id_override_global_tz');

        $overrideGlobalTimezone.click(function () {
            $userTimezone.val($globalTimezone.val());
            $userTimezone.change();
        });

        var $matchMessage = $('<span class="help-block" />');
        $userTimezone.parent().append($matchMessage);

        var $matchTzButton = $('<a href="#" class="btn btn-default" style="margin-left: 1em;" />').text(gettext('Reset to Default'));
        $matchTzButton.click(function () {
            $userTimezone.val($globalTimezone.val());
            $userTimezone.change();
            return false;
        });
        $userTimezone.after($matchTzButton);

        compareGlobalUserTimezones();
        $userTimezone.change(compareGlobalUserTimezones);

        function compareGlobalUserTimezones() {
            if ($globalTimezone.val() === $userTimezone.val()) {
                $userTimezone.parent().parent().addClass('has-success').removeClass('has-warning');
                $matchMessage.html(gettext('This matches the global setting: ') + '<strong>' + $globalTimezone.val() + '</strong>');
            } else {
                $userTimezone.parent().parent().addClass('has-warning').removeClass('has-success');
                $matchMessage.html(gettext('This does not match global setting: ') + '<strong>' + $globalTimezone.val() + '</strong>');
            }
        }

        if (initialPageData.get('no_domain_membership')) {
            var error = gettext("You may not override this project space's timezone because you only have access to this project space through an Organization. " +
                    "You must be added to the project space as a member in order to override your timezone.");
            $overrideGlobalTimezone.parent().html(error);
        }
    });
});
