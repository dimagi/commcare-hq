hqDefine("users/js/web_users", function() {
    'use strict';
    var usersApp = window.angular.module('usersApp', ['hq.web_users']);
    usersApp.config(['$httpProvider', function($httpProvider) {
        $httpProvider.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';
        $httpProvider.defaults.xsrfCookieName = 'csrftoken';
        $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken';
        $httpProvider.defaults.headers.common["X-CSRFToken"] = $("#csrfTokenContainer").val();
    }]);
    usersApp.config(["djangoRMIProvider", function(djangoRMIProvider) {
        djangoRMIProvider.configure(hqImport("hqwebapp/js/initial_page_data").get("djng_current_rmi"));
    }]);

    $(function() {
        function selectText(element) {
            /* copied from http://stackoverflow.com/questions/985272/jquery-selecting-text-in-an-element-akin-to-highlighting-with-your-mouse */
            var doc = document,
                text = element[0],
                range;

            if (doc.body.createTextRange) { // ms
                range = doc.body.createTextRange();
                range.moveToElementText(text);
                range.select();
            } else if (window.getSelection) { // moz, opera, webkit
                var selection = window.getSelection();
                range = doc.createRange();
                range.selectNodeContents(text);
                selection.removeAllRanges();
                selection.addRange(range);
            }
        }
        $('#adminEmails').on('shown.bs.collapse', function() {
            selectText($('#adminEmails .panel-body'));
            $(window).trigger('scroll');
        });
    });

    $(function() {
        var url = hqImport("hqwebapp/js/initial_page_data").reverse;
        $('#restrict_users').on('change', function() {
            var $saveButton = $('#save_restrict_option');
            $saveButton
                .prop('disabled', false)
                .removeClass('disabled btn-default')
                .addClass('btn-success')
                .text(gettext("Save"));
        });
        $('#save_restrict_option').click(function(e) {
            var post_url = url("location_restriction_for_users");
            $(this).text('Saving ...');
            $.post(post_url, {
                restrict_users: $('#restrict_users')[0].checked,
            },
            function(data) {
                $('#save_restrict_option')
                    .text(gettext("Saved"))
                    .removeClass('btn-success')
                    .prop('disabled', true)
                    .addClass('disabled btn-default');
            });
            e.preventDefault();
        });

        $('.resend-invite').click(function(e) {
            $(this).addClass('disabled').prop('disabled', true);
            var post_url = url("reinvite_web_user");
            var doc_id = this.getAttribute('data-invite');
            var self = this;
            $.post(post_url, {
                invite: doc_id,
            },
            function(data) {
                $(self).parent().text(data.response);
                self.remove();
            });
            e.preventDefault();
        });

        var $userRolesTable = $('#user-roles-table'),
            initial_page_data = hqImport("hqwebapp/js/initial_page_data").get;
        hqImport('users/js/roles').initUserRoles($userRolesTable, {
            userRoles: initial_page_data("user_roles"),
            defaultRole: initial_page_data("default_role"),
            saveUrl: url("post_user_role"),
            deleteUrl: url("delete_user_role"),
            reportOptions: initial_page_data("report_list"),
            webAppsList: initial_page_data("web_apps_list"),
            allowEdit: initial_page_data("can_edit_roles"),
            canRestrictAccessByLocation: initial_page_data("can_restrict_access_by_location"),
            landingPageChoices: initial_page_data("landing_page_choices"),
        });
        $userRolesTable.show();

        function handleDeletion($el, title, body, post_url) {
            var id = $el.data('id');
            $('#confirm-delete').off('click');
            $('#confirm-delete').on('click', function() {
                var $button = $(this);
                $button.addClass('disabled').prop('disabled', true);
                $.post(post_url, {
                    id: id,
                },
                function() {
                    $el.closest("tr").remove();
                    $button.removeClass('disabled').prop('disabled', false);
                    $('#modal-deletion').modal('hide');
                });
            });
            $('#modal-deletion').find(".modal-title").html(title);
            $('#modal-deletion').find(".modal-body").html($("<p/>").append(body));
            $('#modal-deletion').modal('show');
        }

        $('.delete-request').on('click', function(e) {
            handleDeletion($(this),
                gettext("Delete request"),
                gettext("Are you sure you want to delete this request?"),
                url("delete_request")
            );
            e.preventDefault();
        });
        $('.delete-invitation').on('click', function(e) {
            handleDeletion($(this),
                gettext("Delete invitation"),
                gettext("Are you sure you want to delete this invitation?"),
                url("delete_invitation")
            );
            e.preventDefault();
        });
    });
});
