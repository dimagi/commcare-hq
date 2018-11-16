hqDefine("users/js/web_users",[
    'jquery',
    'knockout',
    'underscore',
    "hqwebapp/js/initial_page_data",
    'users/js/roles',
    'bootstrap', // for bootstrap modal
    'hqwebapp/js/components.ko',    // pagination widget
    'hqwebapp/js/knockout_bindings.ko', // for staticChecked data binding in web_users.html
], function ($, ko, _, initialPageData, userRoles) {

    var webUsersList = function () {
        var self = {};
        self.users = ko.observableArray([]);

        self.query = ko.observable('');

        self.itemsPerPage = ko.observable();
        self.totalItems = ko.observable();

        self.error = ko.observable();
        self.showSpinner = ko.observable(true);
        self.showUsers = ko.computed(function () {
            return !self.showSpinner() && !self.error();
        });

        self.goToPage = function (page) {
            self.users.removeAll();
            self.showSpinner(true);
            self.error('');
            $.ajax({
                method: 'GET',
                url: initialPageData.reverse('paginate_web_users'),
                data: {
                    page: page,
                    query: self.query() || '',
                    limit: self.itemsPerPage(),
                },
                success: function (data) {
                    self.showSpinner(false);
                    self.totalItems(data.total);
                    self.users.removeAll();     // just in case there are multiple goToPage calls simultaneously
                    _.each(data.users, function (user) {
                        self.users.push(user);
                    });
                },
                error: function () {
                    self.showSpinner(false);
                    self.error(gettext("Could not load users. Please try again later or report an issue if this problem persists."));
                },
            });
        };

        return self;
    };

    $(function () {
        $("#web-users-panel").koApplyBindings(webUsersList());
    });

    $(function () {
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
        $('#adminEmails').on('shown.bs.collapse', function () {
            selectText($('#adminEmails .panel-body'));
            $(window).trigger('scroll');
        });
    });

    $(function () {
        var url = initialPageData.reverse;
        $('#restrict_users').on('change', function () {
            var $saveButton = $('#save_restrict_option');
            $saveButton
                .prop('disabled', false)
                .removeClass('disabled btn-default')
                .addClass('btn-success')
                .text(gettext("Save"));
        });
        $('#save_restrict_option').click(function (e) {
            $(this).text(gettext('Saving ...'));
            $.post(url("location_restriction_for_users"), {
                restrict_users: $('#restrict_users')[0].checked,
            },
            function () {
                $('#save_restrict_option')
                    .text(gettext("Saved"))
                    .removeClass('btn-success')
                    .prop('disabled', true)
                    .addClass('disabled btn-default');
            });
            e.preventDefault();
        });

        $('.resend-invite').click(function (e) {
            $(this).addClass('disabled').prop('disabled', true);
            var docId = this.getAttribute('data-invite');
            var self = this;
            $.post(url("reinvite_web_user"), {
                invite: docId,
            },
            function (data) {
                $(self).parent().text(data.response);
                self.remove();
            });
            e.preventDefault();
        });

        var $userRolesTable = $('#user-roles-table');

        userRoles.initUserRoles($userRolesTable, {
            userRoles: initialPageData.get("user_roles"),
            defaultRole: initialPageData.get("default_role"),
            saveUrl: url("post_user_role"),
            deleteUrl: url("delete_user_role"),
            reportOptions: initialPageData.get("report_list"),
            webAppsList: initialPageData.get("web_apps_list"),
            allowEdit: initialPageData.get("can_edit_roles"),
            canRestrictAccessByLocation: initialPageData.get("can_restrict_access_by_location"),
            landingPageChoices: initialPageData.get("landing_page_choices"),
        });
        $userRolesTable.show();

        function handleDeletion($el, title, body, postUrl) {
            var id = $el.data('id');
            $('#confirm-delete').off('click');
            $('#confirm-delete').on('click', function () {
                var $button = $(this);
                $button.addClass('disabled').prop('disabled', true);
                $.post(postUrl, {
                    id: id,
                },
                function () {
                    $el.closest("tr").remove();
                    $button.removeClass('disabled').prop('disabled', false);
                    $('#modal-deletion').modal('hide');
                });
            });
            $('#modal-deletion').find(".modal-title").html(title);
            $('#modal-deletion').find(".modal-body").html($("<p/>").append(body));
            $('#modal-deletion').modal('show');
        }

        $('.delete-request').on('click', function (e) {
            handleDeletion($(this),
                gettext("Delete request"),
                gettext("Are you sure you want to delete this request?"),
                url("delete_request")
            );
            e.preventDefault();
        });
        $('.delete-invitation').on('click', function (e) {
            handleDeletion($(this),
                gettext("Delete invitation"),
                gettext("Are you sure you want to delete this invitation?"),
                url("delete_invitation")
            );
            e.preventDefault();
        });
    });
});
