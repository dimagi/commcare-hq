BaseListViewModel = function (o) {
    'use strict';
    var view_model = {};

    view_model.initial_load = ko.observable(false);

    view_model.data_list = ko.observableArray();

    // track any items that were archived/unarchived asynchronously
    view_model.archive_action_items = ko.observableArray();

    view_model.show_inactive = o.show_inactive;
    view_model.list_url = o.list_url;

    view_model.total = ko.observable(o.total);
    view_model.page_limit = ko.observable(o.limit);
    view_model.max_page = ko.computed(function () {
        return Math.ceil(view_model.total()/view_model.page_limit());
    });
    view_model.current_page = ko.observable(o.start_page);
    view_model.next_page = ko.computed(function () {
        var page = view_model.current_page() + 1;
        if (page > view_model.max_page()) {
            return undefined;
        }
        return page;
    });
    view_model.previous_page = ko.computed(function () {
        var page = view_model.current_page() - 1;
        if (page < 1) {
            return undefined;
        }
        return page;
    });

    view_model.all_pages = ko.computed(function () {
        var last_ind = view_model.max_page()+1;
        if (view_model.max_page() <= 5 || view_model.current_page() <= 3)
            return _.range(1, Math.min(last_ind, 6));
        if (view_model.current_page() >= view_model.max_page()-2)
            return _.range(view_model.max_page()-4, last_ind);
        return _.range(view_model.current_page()-2, Math.min(last_ind, view_model.current_page()+3));
    });

    view_model.update_limit = function (model, event) {
        var elem = $(event.currentTarget);
        view_model.page_limit(elem.val());
        view_model.change_page(1);
    };

    view_model.get_data_index = function (index) {
        return index() + ((view_model.current_page() - 1) * view_model.page_limit()) + 1;
    };

    view_model.take_archive_action = function (action_url, button, data_index) {
        $(button).button('loading');
        data_index = ko.utils.unwrapObservable(data_index);
        $.ajax({
            type: 'POST',
            url: action_url,
            dataType: 'json',
            error: view_model.unsuccessful_archive_action(button, data_index),
            success: view_model.successful_archive_action(button, data_index)
        });
    };

    view_model.successful_archive_action = function (button, index) {
        return function (data) {
            if (data.success) {
                var $modal = $(button).parent().parent().parent().parent();
                $modal.modal('hide');
                $modal.on('hidden.bs.modal', function () {
                    var data_list = view_model.data_list(),
                        actioned = view_model.archive_action_items();
                    actioned.push(data_list[index]);
                    data_list = _.difference(data_list, actioned);
                    view_model.total(view_model.total()-1);
                    view_model.data_list(data_list);
                    view_model.archive_action_items(actioned);
                });
            } else {
                view_model.unsuccessful_archive_action(button, index)(data);
            }
        };
    };

    view_model.unsuccessful_archive_action = function (button, index) {
        return function (data) {
            $(button).button('unsuccessful');
        };
    };

    return view_model;
};

