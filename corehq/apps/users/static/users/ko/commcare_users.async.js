var CommCareUsersViewModel = function (o) {
    'use strict';
    var self = this;
    self.initial_load = ko.observable(false);

    self.users_list = ko.observableArray();
    self.archive_action_users = ko.observableArray();

    self.cannot_share = o.cannot_share;
    self.show_inactive = o.show_inactive;
    self.more_columns = ko.observable(o.more_columns);

    self.list_url = o.list_url;

    self.total = ko.observable(o.total);
    self.page_limit = ko.observable(o.limit);
    self.max_page = ko.computed(function () {
        return Math.ceil(self.total()/self.page_limit());
    });
    self.current_page = ko.observable(o.start_page);
    self.next_page = ko.computed(function () {
        var page = self.current_page() + 1;
        if (page > self.max_page()) {
            return undefined;
        }
        return page;
    });
    self.previous_page = ko.computed(function () {
        var page = self.current_page() - 1;
        if (page < 1) {
            return undefined;
        }
        return page;
    });

    self.all_pages = ko.computed(function () {
        var last_ind = self.max_page()+1;
        if (self.max_page() <= 5 || self.current_page() <= 3)
            return _.range(1, Math.min(last_ind, 6));
        if (self.current_page() >= self.max_page()-2)
            return _.range(self.max_page()-4, last_ind);
        return _.range(self.current_page()-2, Math.min(last_ind, self.current_page()+3));
    });

    self.colspan = ko.computed(function () {
        if (self.more_columns())
            return 8;
        return 7;
    });

    self.init = function () {
        $(function () {
            self.change_page(self.current_page);
        });
    };

    self.update_limit = function (model, event) {
        var elem = $(event.currentTarget);
        self.page_limit(elem.val());
        self.change_page(1);
    };

    self.show_more_columns = function () {
        self.more_columns(true);
        self.change_page(self.current_page);
        return false;
    };

    self.change_page = function (page, next_or_last) {
        page = ko.utils.unwrapObservable(page);

        if (page) {
            $.ajax({
                url: format_url(page),
                dataType: 'json',
                error: function () {
                    self.initial_load(true);
                    $('.hide-until-load').fadeIn();
                    $('#user-list-notification').text('Sorry, there was an problem contacting the server ' +
                        'to fetch your Mobile Workers list. Please, try again in a little bit.');
                },
                success: reloadList
            });
        }

        return false;
    };

    self.get_user_index = function (index) {
        return index() + ((self.current_page() - 1) * self.page_limit()) + 1;
    };

    self.format_phone_numbers = function (numbers) {
        if (numbers.length < 1) {
            return "";
        }
        var first_num = "+" + numbers[0];
        if (numbers.length > 1) {
            first_num = first_num + " (More Available)";
        }
        return first_num;
    };

    self.take_user_action = function (action_url, button, user_index) {
        $(button).button('loading');
        user_index = ko.utils.unwrapObservable(user_index);
        $.ajax({
            url: action_url,
            dataType: 'json',
            error: unsuccessful_archive_action(button, user_index),
            success: successful_archive_action(button, user_index)
        });
    };

    var reloadList = function(data) {
            if (data.success) {
                if (!self.initial_load()) {
                    self.initial_load(true);
                    $('.hide-until-load').fadeIn();
                }
                self.current_page(data.current_page);
                self.users_list(data.users_list);
                self.archive_action_users([]);
            }
        },
        format_url = function(page) {
            if (!page) {
                return "#";
            }
            return self.list_url +'?page=' + page +
                "&limit=" + self.page_limit() +
                "&cannot_share=" + self.cannot_share +
                "&show_inactive=" + self.show_inactive +
                "&more_columns=" + self.more_columns();
        },
        successful_archive_action = function (button, index) {
            return function (data) {
                if (data.success) {
                    var $modal = $(button).parent().parent();
                    $modal.modal('hide');
                    $modal.on('hidden', function () {
                        var users = self.users_list(),
                            actioned = self.archive_action_users();
                        actioned.push(users[index]);
                        users = _.difference(users, actioned);
                        self.total(self.total()-1);
                        self.users_list(users);
                        self.archive_action_users(actioned);
                    });
                } else {
                    unsuccessful_archive_action(button, index)(data);
                }
            }
        },
        unsuccessful_archive_action = function (button, index) {
            return function (data) {
                $(button).button('unsuccessful');
            }
        };
};

$.fn.asyncUsersList = function (options) {
    this.each(function(i, v) {
        var viewModel = new CommCareUsersViewModel(options);
        ko.applyBindings(viewModel, $(this).get(i));
        viewModel.init();
    });
};

ko.bindingHandlers.isPrevNextDisabled = {
    update: function(element, valueAccessor) {
        var value = valueAccessor()();
        if (value === undefined) {
            $(element).parent().addClass('disabled');
        } else {
            $(element).parent().removeClass('disabled');
        }
    }
};

ko.bindingHandlers.isPaginationActive = {
    update: function(element, valueAccessor, allBindingsAccessor) {
        var current_page = valueAccessor()();
        var current_item = parseInt(allBindingsAccessor()['text']);
        if (current_page === current_item) {
            $(element).parent().addClass('active');
        } else {
            $(element).parent().removeClass('active');
        }
    }
};