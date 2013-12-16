var CommtrackProgramsViewModel = function (o) {
    'use strict';
    var self = this;
    self.initial_load = ko.observable(false);

    self.program_list = ko.observableArray();

    self.list_url = o.list_url;

    self.init = function () {
        $(function () {
            $.ajax({
                url: self.list_url,
                dataType: 'json',
                error: function () {
                    self.initial_load(true);
                    $('.hide-until-load').fadeIn();
                    $('#user-list-notification').text('Sorry, there was an problem contacting the server ' +
                        'to fetch the program list. Please, try again in a little bit.');
                },
                success: reloadList
            });
        });
    };

    var reloadList = function(data) {
            if (data.success) {
                if (!self.initial_load()) {
                    self.initial_load(true);
                    $('.hide-until-load').fadeIn();
                }
                self.program_list(data.program_list);
            }
        }
};

var CommtrackProgramEditModel = function (o) {
    var self = this;
    self.initial_load = ko.observable(false);

    self.products = ko.observableArray();

    self.list_url = o.list_url;

    self.total = ko.observable(o.total);
    self.page_limit = ko.observable(o.limit);
    self.max_page = ko.computed(function () {
        return Math.ceil(self.total()/self.page_limit());
    });
    self.current_page = ko.observable(o.current_page);

    self.all_pages = ko.computed(function () {
        var last_ind = self.max_page()+1;
        if (self.max_page() <= 5 || self.current_page() <= 3)
            return _.range(1, Math.min(last_ind, 6));
        if (self.current_page() >= self.max_page()-2)
            return _.range(self.max_page()-4, last_ind);
        return _.range(self.current_page()-2, Math.min(last_ind, self.current_page()+3));
    });
    self.next_page = ko.computed(function () {
        var page = parseInt(self.current_page()) + 1;
        if (page > self.max_page()) {
            console.log(page + ' : ' + self.max_page());
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

    self.init = function () {
        $(function () {
            $.ajax({
                url: self.list_url,
                dataType: 'json',
                error: function () {
                    self.initial_load(true);
                    $('.hide-until-load').fadeIn();
                    $('#user-list-notification').text('Sorry, there was an problem contacting the server ' +
                        'to fetch the program list. Please, try again in a little bit.');
                },
                success: reloadList
            });
        });
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
                        'to fetch the product list. Please, try again in a little bit.');
                },
                success: reloadList
            });
        }

        return false;
    };

    self.update_limit = function (model, event) {
        var elem = $(event.currentTarget);
        self.page_limit(elem.val());
        self.change_page(1);
    };

    var reloadList = function(data) {
            if (data.success) {
                if (!self.initial_load()) {
                    self.initial_load(true);
                    $('.hide-until-load').fadeIn();
                }
                self.current_page(data.current_page);
                self.products(data.products);
            }
        },
        format_url = function(page) {
            if (!page) {
                return "#";
            }
            return self.list_url +'?page=' + page +
                "&limit=" + self.page_limit();
        };
}

$.fn.asyncProgramList = function (options) {
    this.each(function(i, v) {
        var viewModel = new CommtrackProgramsViewModel(options);
        ko.applyBindings(viewModel, $(this).get(i));
        viewModel.init();
    });
};

$.fn.asyncProductList = function (options) {
    this.each(function(i, v) {
        var viewModel = new CommtrackProgramEditModel(options);
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
        console.log(current_page + ':' + current_item)
        if (current_page === current_item) {
            $(element).parent().addClass('active');
        } else {
            $(element).parent().removeClass('active');
        }
    }
};