var CommtrackProductsProgramsViewModel = function (o) {
    'use strict';
    var self = this;
    self.initial_load = ko.observable(false);

    self.data_list = ko.observableArray();

    // track any products that were archived/unarchived
    // asynchronously
    self.archive_action_products = ko.observableArray();

    self.show_inactive = o.show_inactive;

    self.list_url = o.list_url;

    self.total = ko.observable(o.total);
    self.page_limit = ko.observable(o.limit);
    self.max_page = ko.computed(function () {
        return Math.ceil(self.total()/self.page_limit());
    });
    self.current_page = ko.observable(o.start_page);
    self.next_page = ko.computed(function () {
        var page = parseInt(self.current_page()) + 1;
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

    /*
    self.show_more_columns = function () {
        self.more_columns(true);
        self.change_page(self.current_page);
        return false;
    };
    */

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
                        'to fetch the data. Please, try again in a little bit.');
                },
                success: reloadList
            });
        }

        return false;
    };

    self.get_product_index = function (index) {
        return index() + ((self.current_page() - 1) * self.page_limit()) + 1;
    };

    self.take_archive_action = function (action_url, button, product_index) {
        $(button).button('loading');
        product_index = ko.utils.unwrapObservable(product_index);
        $.ajax({
            url: action_url,
            dataType: 'json',
            error: unsuccessful_archive_action(button, product_index),
            success: successful_archive_action(button, product_index)
        });
    };

    var reloadList = function(data) {
            if (data.success) {
                if (!self.initial_load()) {
                    self.initial_load(true);
                    $('.hide-until-load').fadeIn();
                }
                self.current_page(data.current_page);
                self.data_list(data.data_list);
                self.archive_action_products([]);
            }
        },
        format_url = function(page) {
            if (!page) {
                return "#";
            }
            return self.list_url +'?page=' + page +
                "&limit=" + self.page_limit() +
                "&show_inactive=" + self.show_inactive;
        },
        successful_archive_action = function (button, index) {
            return function (data) {
                if (data.success) {
                    var $modal = $(button).parent().parent();
                    $modal.modal('hide');
                    $modal.on('hidden', function () {
                        var products = self.data_list(),
                            actioned = self.archive_action_products();
                        actioned.push(products[index]);
                        products = _.difference(products, actioned);
                        self.total(self.total()-1);
                        self.data_list(products);
                        self.archive_action_products(actioned);
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

$.fn.asyncProgramProductList = function (options) {
    this.each(function(i, v) {
        var viewModel = new CommtrackProductsProgramsViewModel(options);
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
        var current_page = parseInt(valueAccessor()());
        var current_item = parseInt(allBindingsAccessor()['text']);
        if (current_page === current_item) {
            $(element).parent().addClass('active');
        } else {
            $(element).parent().removeClass('active');
        }
    }
};
