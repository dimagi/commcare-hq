/**
 * This file controls the UI for the web users page.
 */
hqDefine("users/js/web_users",[
    'jquery',
    'knockout',
    'underscore',
    'moment/moment',
    "hqwebapp/js/assert_properties",
    "hqwebapp/js/initial_page_data",
    "users/js/web_users_list",
    'hqwebapp/js/bootstrap3/components.ko',    // pagination and search box widgets
    'hqwebapp/js/bootstrap3/knockout_bindings.ko', // for modals
], function ($, ko, _, moment, assertProperties, initialPageData, webUsersList) {

    /* Web Users panel */
    $(function () {
        $("#web-users-panel").koApplyBindings(webUsersList({
            url: initialPageData.reverse('paginate_web_users'),
        }));
    });

    /* Invitations panel */
    var Invitation = function (options) {
        assertProperties.assertRequired(options, ["uuid", "email", "email_marked_as_bounced", "invited_on", "role_label", "email_status"]);
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
            return _.template(gettext("<%- days %> days remaining"))({
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
        self.statusFilter = ko.observable('');
        self.allStatuses = _.uniq(_.map(self.allInvitations(), function (i) {
            return i.email_status;
        }));
        self.itemsPerPage = ko.observable();
        self.totalItems = ko.observable(self.allInvitations().length);
        self.showPagination = ko.computed(function () {
            return self.totalItems() > self.itemsPerPage();
        });
        self.goToPage = function (page) {
            page = page || 1;
            var skip = (page - 1) * self.itemsPerPage();
            var results = _.filter(self.allInvitations(), function (i) {
                var emailFilter = i.email.toLowerCase().indexOf(self.query().toLowerCase()) !== -1;
                var statusFilter = true;
                if (self.statusFilter()) {
                    statusFilter = i.email_status === self.statusFilter();
                }

                return emailFilter && statusFilter;
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

        $('.undeliverable-label').tooltip({
            placement: 'right',
            html: true,
            title: _.template(gettext(
                "We have sent the invitation email to this user but the user's email server " +
                "rejected it. This usually means either the email address is incorrect or your organization " +
                "is blocking emails from our address (<%- fromAddress %>)."
            ))({
                fromAddress: initialPageData.get('fromAddress'),
            }),
        });
    });
});
