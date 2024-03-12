hqDefine('users/js/edit_commcare_user', [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/bootstrap3/alert_user',
    'analytix/js/google',
    'hqwebapp/js/multiselect_utils',
    'users/js/custom_data_fields',
    'locations/js/widgets',
    'jquery-textchange/jquery.textchange',
    'hqwebapp/js/bootstrap3/knockout_bindings.ko',
    'hqwebapp/js/bootstrap3/widgets',
    'registration/js/password',
    'select2/dist/js/select2.full.min',
    'eonasdan-bootstrap-datetimepicker/build/js/bootstrap-datetimepicker.min',
], function (
    $,
    ko,
    initialPageData,
    alertUser,
    googleAnalytics,
    multiselectUtils,
    customDataFields
) {
    var couchUserId = initialPageData.get('couch_user_id');

    $('.verify-button').tooltip();
    $('#id_language').select2({
        placeholder: gettext('Select a language...'),
    });

    $('#add_phone_number').submit(function () {
        document.getElementById('add_phone_number').submit();
        googleAnalytics.track.event('Edit Mobile Worker', 'Update phone number', couchUserId, '', {}, function () {});
        return false;
    });

    $('#reset-password-form').submit(function () {
        $(this).ajaxSubmit({
            url: $(this).attr('action'),
            type: 'POST',
            dataType: 'json',
            success: function (response) {
                if (response.status === "OK") {
                    alertUser.alert_user(gettext("Password changed successfully."), 'success');
                    googleAnalytics.track.event("Edit Mobile Worker", "Reset password", couchUserId);
                } else if (response.status === "weak") {
                    alertUser.alert_user(gettext("Password is not strong enough. " +
                                                 "Try making your password more complex."), 'danger');
                } else if (response.status === "different") {
                    alertUser.alert_user(gettext("The two password fields didn't match."), 'danger');
                } else {
                    alertUser.alert_user(gettext("Password was not changed. "), 'danger');
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
    multiselectUtils.createFullMultiselectWidget('id_selected_ids', {
        selectableHeaderTitle: gettext("Available Groups"),
        selectedHeaderTitle: gettext("Groups with this User"),
        searchItemTitle: gettext("Search Group..."),
    });

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
        $userInformationForm.find(":submit").prop("disabled", false);
    }).on("input", null, null, function () {
        $userInformationForm.find(":submit").prop("disabled", false);
    });

    // Enable deactivate after calendar widget
    let showDeactivateAfterDate = initialPageData.get('show_deactivate_after_date');
    if (showDeactivateAfterDate) {
        $('#id_deactivate_after_date').datetimepicker({
            format: 'MM-y',
        }).on('dp.change', function () {
            $userInformationForm.trigger('change');
        });
    }

    /* Additional Information / custom user data */
    var $customDataFieldsForm = $(".custom-data-fieldset");
    if ($customDataFieldsForm.length) {
        $customDataFieldsForm.koApplyBindings(function () {
            return {
                custom_fields: customDataFields.customDataFieldsEditor({
                    user_data: initialPageData.get('user_data'),
                    profiles: initialPageData.get('custom_fields_profiles'),
                    profile_slug: initialPageData.get('custom_fields_profile_slug'),
                    slugs: initialPageData.get('custom_fields_slugs'),
                }),
            };
        });
    }

    // If there's unrecognized data, allow user to save to clear it
    var $unrecognizedDataWarning = $("#js-unrecognized-data");
    if ($unrecognizedDataWarning.length > 0) {
        $unrecognizedDataWarning.closest("form").find(":submit").prop("disabled", false);
    }

    // Analytics
    $("button:submit", $userInformationForm).on("click", function () {
        $userInformationForm.submit();
        googleAnalytics.track.event("Edit Mobile Worker", "Updated user info", couchUserId, "", {});
        return false;
    });
});
