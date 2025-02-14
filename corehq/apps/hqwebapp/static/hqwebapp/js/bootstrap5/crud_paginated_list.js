// side effects: defines knockout bindings that are used in hqwebapp/partials/pagination.html
hqDefine("hqwebapp/js/bootstrap5/crud_paginated_list", [
    "jquery",
    "knockout",
    "underscore",
    "es6!hqwebapp/js/bootstrap5_loader",
    'hqwebapp/js/bootstrap5/knockout_bindings.ko',  // fadeVisible
], function (
    $,
    ko,
    _,
    bootstrap,
) {
    var CRUDPaginatedListModel = function (
        total,
        pageLimit,
        currentPage,
        options,
        paginatedItem,
    ) {
        options = options || {};

        var self = {};

        self.PaginatedItem = paginatedItem || PaginatedItem;

        self.sortBy = options.sortBy || 'abc';

        self.hasInitialLoadFinished = ko.observable(false);

        self.createItemForm = ko.observable($(options.createItemForm).html());
        self.createItemFormClass = ko.observable(options.createItemFormClass);
        self.isCreateItemVisible = ko.computed(function () {
            return Boolean(self.createItemForm());
        });

        self.alertHtml = ko.observable();
        self.isAlertVisible = ko.computed(function () {
            return Boolean(self.alertHtml());
        });

        self.isLoadingVisible = ko.computed(function () {
            return !self.hasInitialLoadFinished();
        });

        self.total = ko.observable(total);
        self.pageLimit = ko.observable(pageLimit);

        self.paginatedList = ko.observableArray();  // the list of data to be paginated
        self.newList = ko.observableArray(); // the list of data that was created
        self.deletedList = ko.observableArray();  // the list of data that was modified

        self.isPaginationActive = ko.computed(function () {
            return self.total() > 0;
        });

        self.isPaginationTableVisible = ko.computed(function () {
            return self.isPaginationActive() || self.isCreateItemVisible();
        });

        self.isPaginatedListEmpty = ko.computed(function () {
            return self.paginatedList().length === 0;
        });

        self.isNewListVisible = ko.computed(function () {
            return self.newList().length > 0;
        });

        self.isDeletedListVisible = ko.computed(function () {
            return self.deletedList().length > 0;
        });

        self.maxPage = ko.computed(function () {
            return Math.ceil(self.total() / self.pageLimit());
        });
        self.currentPage = ko.observable(currentPage);
        self.nextPage = ko.computed(function () {
            var page = self.currentPage() + 1;
            if (page > self.maxPage()) {
                return undefined;
            }
            return page;
        });
        self.previousPage = ko.computed(function () {
            var page = self.currentPage() - 1;
            if (page < 1) {
                return undefined;
            }
            return page;
        });

        self.allPages = ko.computed(function () {
            var lastIndex = self.maxPage() + 1;
            if (self.maxPage() <= 5 || self.currentPage() <= 3) {
                return _.range(1, Math.min(lastIndex, 6));
            }
            if (self.currentPage() >= self.maxPage() - 2) {
                return _.range(self.maxPage() - 4, lastIndex);
            }
            return _.range(self.currentPage() - 2, Math.min(lastIndex, self.currentPage() + 3));
        });

        self.utils = {
            reloadList: function (data) {
                if (data.success) {
                    if (!self.hasInitialLoadFinished()) {
                        self.hasInitialLoadFinished(true);

                    }
                    self.currentPage(data.currentPage);
                    if (data.total !== null) {
                        self.total(data.total);
                    }
                    self.paginatedList(_.map(
                        data.paginatedList,
                        function (listItem) {
                            return self.PaginatedItem(listItem, self.initRow);
                        },
                    ));
                    self.deletedList([]);
                    self.newList([]);
                }
            },
        };

        // Error & Success Handling
        self.statusCodeText = options.statusCodeText || {
            '404': "Sorry, not found",
            '500': "Server error.",
        };

        self.handleStatusCode = {};
        _.each(self.statusCodeText, function (statusText, statusCode) {
            self.handleStatusCode[statusCode] = function () {
                self.alertHtml(statusText);
            };
        });

        // Actions
        self.init = function () {
            $(function () {
                self.changePage(self.currentPage);
                if (self.isCreateItemVisible()) {
                    self.initCreateForm();
                }
            });
        };

        self.initCreateForm = function () {
            const $createForm = $("#create-item-form");
            $createForm.submit(function (e) {
                e.preventDefault();
                let formData = new FormData($createForm.get(0));
                formData.set("action", "create");
                $.ajax({
                    method: 'POST',
                    dataType: 'json',
                    data: Object.fromEntries(formData),
                    statusCode: self.handleStatusCode,
                    success: function (data) {
                        $createForm[0].reset();
                        self.createItemForm($(data.form).html());
                        if (data.newItem) {
                            if (data.newItem.error) {
                                self.alertHtml(data.newItem.error);
                            } else {
                                self.newList.push(self.PaginatedItem(data.newItem, self.initRow));
                            }
                        }
                    },
                });
            });
        };

        self.changePage = function (page) {
            page = ko.utils.unwrapObservable(page);
            if (page) {
                $.ajax({
                    url: "",
                    type: 'post',
                    dataType: 'json',
                    data: {
                        action: 'paginate',
                        page: page,
                        limit: self.pageLimit(),
                        sortBy: self.sortBy,
                        additionalData: self.getAdditionalData(),
                    },
                    statusCode: self.handleStatusCode,
                    success: function (data) {
                        self.utils.reloadList(data);
                    },
                });
            }
        };

        self.updateListLimit = function (model, event) {
            var elem = $(event.currentTarget);
            self.pageLimit(elem.val());
            self.changePage(1);
        };

        self.deleteItem = function (paginatedItem, event, button) {
            var pList = self.paginatedList();
            $(button).enableButton();
            paginatedItem.dismissModals();
            self.paginatedList(_(pList).without(paginatedItem));
            self.deletedList.push(paginatedItem);
            $.ajax({
                url: "",
                type: 'post',
                dataType: 'json',
                data: {
                    action: 'delete',
                    itemId: paginatedItem.itemId,
                },
                statusCode: self.handleStatusCode,
                success: function (data) {
                    if (data.error) {
                        self.alertHtml(data.error);
                    }
                    if (data.deletedItem) {
                        paginatedItem.updateItemSpec(data.deletedItem);
                    }
                },
            });
        };

        self.refreshList = function (paginatedItem, button) {
            $.ajax({
                url: '',
                type: 'post',
                dataType: 'json',
                data: {
                    action: 'refresh',
                    itemId: (paginatedItem) ? paginatedItem.itemId : null,
                    page: self.currentPage(),
                    limit: self.pageLimit(),
                    sortBy: self.sortBy,
                    additionalData: self.getAdditionalData(),
                },
                statusCode: self.handleStatusCode,
                success: function (data) {
                    self.utils.reloadList(data);
                    $(button).enableButton();
                },
            });
        };

        self.getAdditionalData = function () {
            return null;
        };

        self.initRow = function () {
            // Intended to be overridden with additional initialization for
            // each row in the paginated list.
            // Arguments: rowElems, paginatedItem
        };

        return self;
    };

    var PaginatedItem = function (itemSpec, initRow) {
        var self = {};
        self.itemId = itemSpec.itemData.id;
        self.itemRowId = 'item-row-' + self.itemId;
        self.itemData = ko.observable(itemSpec.itemData);
        self.template = ko.observable(itemSpec.template);
        self.rowClass = ko.observable(itemSpec.rowClass);
        self.initRow = initRow;

        self.getItemRow = function () {
            return $('#' + self.itemRowId);
        };

        self.dismissModals = function () {
            var $modal = self.getItemRow().find('.modal');
            if ($modal) {
                bootstrap.Modal.getOrCreateInstance($modal).hide();
            }
        };

        self.updateItemSpec = function (data) {
            if (data.template) {
                self.template(data.template);
            }
            if (data.itemData) {
                self.itemData(data.itemData);
            }
            if (data.rowClass) {
                self.rowClass(data.rowClass);
            }
        };

        self.initTemplate = function (elems) {
            var $updateForm = $(elems).find('.update-item-form');
            if ($updateForm) {
                $updateForm.submit(function (e) {
                    let formData = new FormData($updateForm.get(0));
                    formData.set("action", "update");
                    e.preventDefault();
                    $.ajax({
                        method: 'POST',
                        data: Object.fromEntries(formData),
                        success: function (data) {
                            if (data.updatedItem) {
                                self.dismissModals();
                                self.updateItemSpec(data.updatedItem);
                            } else if (data.form) {
                                var $updateForm = self.getItemRow().find('.update-item-form');
                                if ($updateForm) {
                                    $updateForm.html($(data.form).html());
                                }
                            }
                        },
                    });
                });
            }
            var $deleteButton = $(elems).find('.delete-item-confirm');
            if ($deleteButton) {
                $deleteButton.click(function () {
                    $(this).disableButton();
                    self.getItemRow().trigger('deleteItem', this);
                });
            }
            var $refreshButton = $(elems).find('.refresh-list-confirm');
            if ($refreshButton) {
                $refreshButton.click(function () {
                    $(this).disableButton();
                    self.getItemRow().trigger('refreshList', this);
                });
            }
            self.initRow(elems, self);
        };

        return self;
    };

    ko.bindingHandlers.disabledOnUndefined = {
        update: function (element, valueAccessor) {
            var value = valueAccessor()();
            if (value === undefined) {
                $(element).addClass('disabled');
            } else {
                $(element).removeClass('disabled');
            }
        },
    };

    ko.bindingHandlers.activeOnSimilar = {
        update: function (element, valueAccessor, allBindingsAccessor) {
            var current = valueAccessor()();
            var compare = parseInt(allBindingsAccessor()['compareText']);
            if (current === compare) {
                $(element).addClass('active');
            } else {
                $(element).removeClass('active');
            }
        },
    };

    return {
        CRUDPaginatedListModel: CRUDPaginatedListModel,
        PaginatedItem: PaginatedItem,
    };
});
