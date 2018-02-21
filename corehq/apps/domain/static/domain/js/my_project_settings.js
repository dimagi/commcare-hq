hqDefine("domain/js/my_project_settings", function() {
    var HQTimezoneHandler = function (o) {
        'use strict';
        var self = this;
        self.override_tz = ko.observable(o.override);
        self.form_is_ready = ko.observable(false);

        self.updateForm = function() {
            self.form_is_ready(true);
        };
    };

    $(function() {
        var initial_page_data = hqImport('hqwebapp/js/initial_page_data').get;
        $('#my-project-settings-form').koApplyBindings(new HQTimezoneHandler({
            override: initial_page_data('override_global_tz'),
        }));

        var $globalTimezone = $('#id_global_timezone'),
            $userTimezone = $('#id_user_timezone'),
            $overrideGlobalTimezone = $('#id_override_global_tz');

        var $matchMessage = $('<span class="help-block" />');
        $userTimezone.parent().append($matchMessage);

        var $matchTzButton = $('<a href="#" class="btn btn-default" style="margin-left: 1em;" />').text(gettext('Reset to Default'));
        $matchTzButton.click(function () {
            $userTimezone.val($globalTimezone.val());
            $userTimezone.change();
            return false;
        });
        $userTimezone.after($matchTzButton);

        compare_global_user_timezones();
        $userTimezone.change(compare_global_user_timezones);

        $('#update-proj-settings').click(function () {
            if ($(this).hasClass('disabled'))
                return false;
        });

        function compare_global_user_timezones() {
            if($globalTimezone.val() === $userTimezone.val()) {
                $userTimezone.parent().parent().addClass('has-success').removeClass('has-warning');
                $matchMessage.html(gettext('This matches the global setting: ') + '<strong>' + $globalTimezone.val() + '</strong>');
            } else {
                $userTimezone.parent().parent().addClass('has-warning').removeClass('has-success');
                $matchMessage.html(gettext('This does not match global setting: ') + '<strong>' + $globalTimezone.val() + '</strong>');
            }
        }

        if (initial_page_data('no_domain_membership')) {
            var err_txt = "You may not override this project space's timezone because you only have access to this project space through an Organization. " +
                    "You must be added to the project space as a member in order to override your timezone.";
            $overrideGlobalTimezone.parent().html(err_txt);
        }
    });
});
