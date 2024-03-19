hqDefine("commtrack/js/bootstrap5/base_list_view_model", [
    'jquery',
    'knockout',
    'underscore',
    'es6!hqwebapp/js/bootstrap5_loader',
], function (
    $,
    ko,
    _,
    bootstrap
) {
    var BaseListViewModel = function (o) {
        'use strict';
        var self = {};

        self.initialLoad = ko.observable(false);

        self.dataList = ko.observableArray();

        // track any items that were archived/unarchived asynchronously
        self.archiveActionItems = ko.observableArray();

        self.showInactive = o.show_inactive;
        self.listURL = o.list_url;

        self.total = ko.observable(o.total);
        self.pageLimit = ko.observable(o.limit);
        self.max_page = ko.computed(function () {
            return Math.ceil(self.total() / self.pageLimit());
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
            var lastInd = self.max_page() + 1;
            if (self.max_page() <= 5 || self.current_page() <= 3) {
                return _.range(1, Math.min(lastInd, 6));
            }
            if (self.current_page() >= self.max_page() - 2) {
                return _.range(self.max_page() - 4, lastInd);
            }
            return _.range(self.current_page() - 2, Math.min(lastInd, self.current_page() + 3));
        });

        self.update_limit = function (model, event) {
            var elem = $(event.currentTarget);
            self.pageLimit(elem.val());
            self.change_page(1);
        };

        self.getDataIndex = function (index) {
            return index() + ((self.current_page() - 1) * self.pageLimit()) + 1;
        };

        self.takeArchiveAction = function (actionUrl, button, dataIndex) {
            $(button).button('loading');
            dataIndex = ko.utils.unwrapObservable(dataIndex);
            $.ajax({
                type: 'POST',
                url: actionUrl,
                dataType: 'json',
                error: self.unsuccessfulArchiveAction(button),
                success: self.successfulArchiveAction(button, dataIndex),
            });
        };

        self.successfulArchiveAction = function (button, index) {
            return function (data) {
                if (data.success) {
                    var $modal = $(button).closest(".modal"),
                        modal = bootstrap.Modal.getOrCreateInstance($modal);
                    modal.hide();
                    $modal.one('hidden.bs.modal', function () {
                        var dataList = self.dataList(),
                            actioned = self.archiveActionItems();
                        actioned.push(dataList[index]);
                        dataList = _.difference(dataList, actioned);
                        self.total(self.total() - 1);
                        self.dataList(dataList);
                        self.archiveActionItems(actioned);
                    });
                } else {
                    self.unsuccessfulArchiveAction(button)(data);
                }
            };
        };

        self.unsuccessfulArchiveAction = function (button) {
            return function () {
                $(button).button('unsuccessful');
            };
        };

        return self;
    };

    return {
        BaseListViewModel: BaseListViewModel,
    };
});
