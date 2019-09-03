hqDefine('users/js/edit_commcare_user', [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/alert_user',
    'analytix/js/google',
    'hqwebapp/js/multiselect_utils',
    'jquery-textchange/jquery.textchange',
    'hqwebapp/js/widgets',
    'registration/js/password',
    'nic_compliance/js/encoder',
    'select2/dist/js/select2.full.min',
    'hqwebapp/js/ui_elements/ui-element-langcode-button',
    'hqwebapp/js/ui_elements/ui-element-input',
    'hqwebapp/js/ui_elements/ui-element-checkbox',
    'hqwebapp/js/ui_elements/ui-element-input-map',
    'hqwebapp/js/ui_elements/ui-element-key-val-list',
    'hqwebapp/js/ui_elements/ui-element-key-val-mapping',
    'hqwebapp/js/ui_elements/ui-element-select',
    'hqwebapp/js/ui-element', // todo cleanup ui-element imports
], function (
    $,
    ko,
    initialPageData,
    alertUser,
    googleAnalytics,
    multiselectUtils
) {
    var couchUserId = initialPageData.get('couch_user_id');

    $('.verify-button').tooltip();
    $('#id_language').select2({
        placeholder: gettext('Select a language...'),
    });

    $('#add_phone_number').submit(function () {
        googleAnalytics.track.event('Edit Mobile Worker', 'Update phone number', couchUserId, '', {}, function () {
            document.getElementById('add_phone_number').submit();
        });
        return false;
    });

    $('#reset-password-form').submit(function () {
        $(this).ajaxSubmit({
            url: $(this).attr('action'),
            type: 'POST',
            dataType: 'json',
            success: function (response, status, xhr, form) {
                form.find('#user-password').html(response.formHTML);
                if (response.status === "OK") {
                    alertUser.alert_user(gettext("Password changed successfully"), 'success');
                    googleAnalytics.track.event("Edit Mobile Worker", "Reset password", couchUserId);
                } else {
                    var message = gettext('Password was not changed ');
                    if (initialPageData.get('hide_password_feedback')) {
                        message += gettext("Password Requirements: 1 special character, " +
                            "1 number, 1 capital letter, minimum length of 8 characters.");
                    }
                    alertUser.alert_user(message, 'danger');
                }
            },
        });
        return false;
    });
    if (!initialPageData.get('is_currently_logged_in_user')) {
        var deleteUserButtonModel = function () {
            var self = {};
            self.signOff = ko.observable('');
            self.formDeleteUserSent = ko.observable(false);
            self.disabled = function () {
                if (!initialPageData.get('is_delete_allowed')) {
                    return true;
                }
                var understand = self.signOff().toLowerCase() === initialPageData.get('couch_user_username');
                return self.formDeleteUserSent() || !understand;
            };
            self.submit = function () {
                if (!self.disabled()) {
                    self.formDeleteUserSent(true);
                    return true;
                }
            };
            return self;
        };
        if ($('#delete_user_' + couchUserId).get(0)) {
            $('#delete_user_' + couchUserId).koApplyBindings(deleteUserButtonModel());
        }

        // Event tracking
        var $deleteModalForm = $("#delete_user_" + couchUserId + " form");
        $("button:submit", $deleteModalForm).on("click", function () {
            googleAnalytics.track.event("Edit Mobile Worker", "Deleted User", couchUserId, "", {}, function () {
                $deleteModalForm.submit();
            });
            return false;
        });

    }

    // Groups form
    multiselectUtils.createFullMultiselectWidget(
        'id_selected_ids',
        gettext("Available Groups"),
        gettext("Groups with this User"),
        gettext("Search Group...")
    );

    // "are you sure?" stuff
    var unsavedChanges = false;
    $("#id_selected_ids").change(function () {
        unsavedChanges = true;
    });

    $(window).on('beforeunload', function () {
        if (unsavedChanges) {
            return gettext("Group membership has changed.");
        }
    });
    $("#groups").submit(function () {
        $(window).unbind("beforeunload");
    });

    // Input handling
    $('#id_add_phone_number').on('paste', function (event) {
        var clipboardData = event.clipboardData || event.originalEvent.clipboardData;
        var pasteText = clipboardData.getData("Text");
        var text = pasteText.replace(/\+|-|\(|\)|\s/g, '');
        if (/^[0-9]*$/.test(text)) {
            $("#phone_number_paste_error").css("display", "none");
            $('#id_add_phone_number').val(text);
        } else {
            $("#phone_number_paste_error").css("display", "inline");
        }
        return false;
    });

    var $userInformationForm = $('form[name="user_information"]');
    $userInformationForm.on("change", null, null, function () {
        $(":submit").prop("disabled", false);
    }).on("input", null, null, function () {
        $(":submit").prop("disabled", false);
    });

    if ($('#js-unrecognized-data').length > 0) {
        $(":submit").prop("disabled", false);
    }

    // Analytics
    $("button:submit", $userInformationForm).on("click", function () {
        googleAnalytics.track.event("Edit Mobile Worker", "Updated user info", couchUserId, "", {}, function () {
            $userInformationForm.submit();
        });
        return false;
    });
});
