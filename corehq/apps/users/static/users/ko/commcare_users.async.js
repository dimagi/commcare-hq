var CommCareUsersViewModel = function (o) {
    var view_model = BaseListViewModel(o);

    view_model.cannot_share = o.cannot_share;
    view_model.more_columns = ko.observable(o.more_columns);

    view_model.colspan = ko.computed(function () {
        if (view_model.more_columns())
            return 8;
        return 7;
    });

    view_model.search_string = ko.observable();
    view_model.from_search = ko.observable();
    view_model.currently_searching = ko.observable(false);

    view_model.init = function () {
        $(function () {
            view_model.change_page(view_model.current_page);
            $("#user-search-clear-btn").click(function(e) {
                view_model.search_string('');
            });
        });
    };

    view_model.show_more_columns = function () {
        view_model.more_columns(true);
        view_model.change_page(view_model.current_page);
        return false;
    };

    view_model.change_page = function (page, next_or_last) {
        page = ko.utils.unwrapObservable(page);
        view_model.from_search(page === -1);
        page = page === -1 ? 1 : page;

        if (page) {
            view_model.currently_searching(true);
            $.ajax({
                url: format_url(page),
                dataType: 'json',
                error: function () {
                    view_model.initial_load(true);
                    $('.hide-until-load').fadeIn();
                    $('#user-list-notification').text('Sorry, there was an problem contacting the server ' +
                        'to fetch your Mobile Workers list. Please, try again in a little bit.');
                    view_model.currently_searching(false);
                },
                success: reloadList
            });
        }

        return false;
    };

    view_model.format_phone_numbers = function (numbers) {
        if (numbers.length < 1) {
            return "";
        }
        var first_num = "+" + numbers[0];
        if (numbers.length > 1) {
            first_num = first_num + " (More Available)";
        }
        return first_num;
    };

    var reloadList = function(data) {
        view_model.currently_searching(false);
        if (data.success) {
            if (!view_model.initial_load()) {
                view_model.initial_load(true);
                $('.hide-until-load').fadeIn();
            }
            view_model.current_page(data.current_page);
            view_model.data_list(data.data_list);
            view_model.total(data.data_list_total);
            view_model.archive_action_items([]);
        }
    }

    var format_url = function(page) {
        if (!page) {
            return "#";
        }
        var ret_url = view_model.list_url +'?page=' + page +
            "&limit=" + view_model.page_limit() +
            "&cannot_share=" + view_model.cannot_share +
            "&show_inactive=" + view_model.show_inactive +
            "&more_columns=" + view_model.more_columns();

        if (view_model.search_string()) {
            ret_url += "&query=" + view_model.search_string();
        }

        return ret_url
    }

    return view_model;
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
