hqDefine("users/js/web_users",[
    'jquery',
    'knockout',
    'underscore',
    "hqwebapp/js/initial_page_data",
    'bootstrap', // for bootstrap modal
    'hqwebapp/js/components.ko',    // pagination widget
    'hqwebapp/js/knockout_bindings.ko', // for modals
], function ($, ko, _, initialPageData) {

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
