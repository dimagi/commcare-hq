var CommtrackProductsProgramsViewModel = function (o) {
    var view_model = BaseListViewModel(o);

    view_model.colspan = ko.computed(function () {
        return 7;
    });

    view_model.init = function () {
        $(function () {
            view_model.change_page(view_model.current_page);
        });
    };

    view_model.change_page = function (page, next_or_last) {
        page = ko.utils.unwrapObservable(page);

        if (page) {
            $.ajax({
                url: format_url(page),
                dataType: 'json',
                error: function () {
                    view_model.initial_load(true);
                    $('.hide-until-load').fadeIn();
                    $('#user-list-notification').text('Sorry, there was an problem contacting the server ' +
                        'to fetch the data. Please, try again in a little bit.');
                },
                success: reloadList
            });
        }

        return false;
    };

    var reloadList = function(data) {
        if (data.success) {
            if (!view_model.initial_load()) {
                view_model.initial_load(true);
                $('.hide-until-load').fadeIn();
            }
            view_model.current_page(data.current_page);
            view_model.data_list(data.data_list);
            view_model.archive_action_items([]);
        }
    }
    var format_url = function(page) {
        if (!page) {
            return "#";
        }
        return view_model.list_url +'?page=' + page +
            "&limit=" + view_model.page_limit() +
            "&show_inactive=" + view_model.show_inactive;
    }

    return view_model;
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
