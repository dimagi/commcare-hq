hqDefine("users/js/web_users",[
    'jquery',
    'knockout',
    'underscore',
    'moment/moment',
    "hqwebapp/js/assert_properties",
    "hqwebapp/js/initial_page_data",
    'bootstrap', // for bootstrap modal
    'hqwebapp/js/components.ko',    // pagination and search box widgets
    'hqwebapp/js/knockout_bindings.ko', // for modals
], function ($, ko, _, moment, assertProperties, initialPageData) {

    /* Web Users panel */
    var webUsersList = function () {
        var self = {};
        self.users = ko.observableArray([]);

        self.query = ko.observable('');

        self.itemsPerPage = ko.observable();
        self.totalItems = ko.observable();

        self.error = ko.observable();
        self.showLoadingSpinner = ko.observable(true);
        self.showPaginationSpinner = ko.observable(false);
        self.showUsers = ko.computed(function () {
            return !self.showLoadingSpinner() && !self.error() && self.users().length > 0;
        });

        self.noUsersMessage = ko.computed(function () {
            if (!self.showLoadingSpinner() && !self.error() && self.users().length === 0) {
                if (self.query()) {
                    return gettext("No users matched your search.");
                }
                return gettext("This project has no web users. Please invite a web user above.");
            }
            return "";
        });

        self.goToPage = function (page) {
            self.showPaginationSpinner(true);
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
                    self.showLoadingSpinner(false);
                    self.showPaginationSpinner(false);
                    self.totalItems(data.total);
                    self.users.removeAll();
                    _.each(data.users, function (user) {
                        self.users.push(user);
                    });
                },
                error: function () {
                    self.showLoadingSpinner(false);
                    self.showPaginationSpinner(false);
                    self.error(gettext("Could not load users. Please try again later or report an issue if this problem persists."));
                },
            });
        };

        self.onPaginationLoad = function () {
            self.goToPage(1);
        };

        return self;
    };

    $(function () {
        $("#web-users-panel").koApplyBindings(webUsersList());
    });

    /* Invitations panel */
    var Invitation = function (options) {
        assertProperties.assertRequired(options, ["uuid", "email", "email_marked_as_bounced", "invited_on", "role_label"]);
        var self = _.extend({}, options);
        self.invited_on = ko.observable(new Date(self.invited_on));
        self.invitedOnText = ko.computed(function () {
            return moment(self.invited_on()).format("MMMM Do YYYY, h:mm a");
        });

        self.daysRemaining = ko.computed(function () {
            var expirationDate = new Date(self.invited_on());
            expirationDate.setDate(expirationDate.getDate() + 31);
            return (expirationDate - new Date()) / (24 * 60 * 60 * 1000);
        });
        self.isExpired = ko.computed(function () {
            return self.daysRemaining() < 0;
        });
        self.daysRemainingText = ko.computed(function () {
            return _.template(gettext("<%= days %> days remaining"))({
                days: Math.floor(self.daysRemaining()),
            });
        });

        self.actionMessage = ko.observable('');
        self.actionInProgress = ko.observable(false);

        self.visible = ko.observable(true);
        self.remove = function () {
            self.actionInProgress(true);
            $.ajax(initialPageData.reverse("delete_invitation"), {
                method: 'POST',
                dataType: 'json',
                data: {
                    uuid: self.uuid,
                },
                success: function () {
                    self.actionInProgress(false);
                    self.visible(false);
                },
                error: function () {
                    self.actionInProgress(false);
                    self.actionMessage(gettext("Unable to delete invitation, please try again later."));
                },
            });
        };

        self.resend = function () {
            self.actionInProgress(true);
            $.ajax(initialPageData.reverse("reinvite_web_user"), {
                method: 'POST',
                dataType: 'json',
                data: {
                    uuid: self.uuid,
                },
                success: function (data) {
                    self.actionInProgress(false);
                    self.actionMessage(data.response);
                    self.invited_on(new Date());
                },
                error: function () {
                    self.actionInProgress(false);
                    self.actionMessage(gettext("Unable to resend invitation, please try again later."));
                },
            });
        };

        return self;
    };

    var invitationsList = function (invitations) {
        var self = {};
        self.allInvitations = ko.observableArray(_.map(invitations, Invitation));
        self.currentPageInvitations = ko.observableArray();

        self.invitationToRemove = ko.observable();
        self.confirmRemoveInvitation = function (model) {
            self.invitationToRemove(model);
        };
        self.removeInvitation = function () {
            self.invitationToRemove().remove();
            self.invitationToRemove(null);
        };
        _.each(self.allInvitations(), function (i) {
            // Invitations can be deleted, but not added back
            i.visible.subscribe(function (newValue) {
                if (!newValue) {
                    self.allInvitations.remove(i);
                    self.totalItems(self.totalItems() - 1);
                }
            });
        });

        self.query = ko.observable('');
        self.itemsPerPage = ko.observable();
        self.totalItems = ko.observable(self.allInvitations().length);
        self.showPagination = ko.computed(function () {
            return self.totalItems() > self.itemsPerPage();
        });
        self.goToPage = function (page) {
            page = page || 1;
            var skip = (page - 1) * self.itemsPerPage();
            var results = _.filter(self.allInvitations(), function (i) {
                return i.email.toLowerCase().indexOf(self.query().toLowerCase()) !== -1;
            });

            self.currentPageInvitations(results.slice(skip, skip + self.itemsPerPage()));
            self.totalItems(results.length);
        };

        self.goToPage(1);

        return self;
    };

    $(function () {
        $("#invitations-panel").koApplyBindings(invitationsList(initialPageData.get('invitations')));
    });

    /* "Copy and paste admin emails" panel */
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

    /* "Pending Access Requests" panel */
    $(function () {
        function handleDeletion($el, data, title, body, postUrl) {
            $('#confirm-delete').off('click');
            $('#confirm-delete').on('click', function () {
                var $button = $(this);
                $button.addClass('disabled').prop('disabled', true);
                $.post(postUrl, data, function () {
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
                {id: $(this).data('id')},
                gettext("Delete request"),
                gettext("Are you sure you want to delete this request?"),
                initialPageData.reverse("delete_request")
            );
            e.preventDefault();
        });
    });
});
