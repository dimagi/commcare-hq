var CRUDPaginatedListModel = function (
    crudURL,
    total,
    pageLimit,
    currentPage,
    options
) {
    'use strict';
    options = options || {};

    var self = this;

    self.hasInitialLoadFinished = ko.observable(false);

    self.createItemForm = ko.observable($(options.createItemForm).html());
    self.isCreateItemVisible = ko.computed(function () {
        return Boolean(self.createItemForm());
    });

    self.alertHtml = ko.observable();
    self.isAlertVisible = ko.computed(function () {
        return Boolean(self.alertHtml())
    });

    self.isLoadingVisible = ko.computed(function () {
        return !self.hasInitialLoadFinished();
    });

    self.paginatedList = ko.observableArray();  // the list of data to be paginated
    self.newList = ko.observableArray(); // the list of data that was created
    self.modifiedList = ko.observableArray();  // the list of data that was modified

    self.isPaginationActive = ko.computed(function () {
        return (self.paginatedList().length + self.modifiedList().length + self.newList().length) > 0;
    });

    self.isPaginationTableVisible = ko.computed(function () {
        return self.isPaginationActive() || self.isCreateItemVisible();
    });

    self.isPaginatedListEmpty = ko.computed(function () {
        return self.paginatedList().length == 0;
    });

    self.isNewListVisible = ko.computed(function () {
        return self.newList().length > 0;
    });

    self.isModifiedListVisible = ko.computed(function () {
        return self.modifiedList().length > 0;
    });

    self.crudURL = crudURL;  // the url we'll be fetching data from

    self.total = ko.observable(total);
    self.pageLimit = ko.observable(pageLimit);
    self.maxPage = ko.computed(function () {
        return Math.ceil(self.total()/self.pageLimit());
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
        var last_ind = self.maxPage() + 1;
        if (self.maxPage() <= 5 || self.currentPage() <= 3)
            return _.range(1, Math.min(last_ind, 6));
        if (self.currentPage() >= self.maxPage() - 2)
            return _.range(self.maxPage() - 4, last_ind);
        return _.range(self.currentPage() - 2, Math.min(last_ind, self.currentPage() + 3));
    });

    self.utils = {
        formatUrl: function (page) {
            if (!page) {
                return '#';
            }
            return self.crudURL +
                '?page=' + page +
                '&limit=' + self.pageLimit();
        },
        reloadList: function (data) {
            if (data.success) {
                if (!self.hasInitialLoadFinished()) {
                    self.hasInitialLoadFinished(true);

                }
                self.currentPage(data.currentPage);
                self.paginatedList(_.map(
                    data.paginatedList,
                    function (listItem) {
                        return new PaginatedItem(listItem);
                    }
                ));
                self.modifiedList([]);
                self.newList([]);
            }
        }
    };

    // Error & Success Handling
    self.statusCodeText = options.statusCodeText || {
        '404': "Sorry, not found",
        '500': "Server error."
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
        })
    };

    self.initCreateForm = function () {
        var $createForm = $("#create-item-form");
        $createForm.submit(function (e) {
            e.preventDefault();
            $createForm.ajaxSubmit({
                url: "",
                type: 'post',
                dataType: 'json',
                data: {
                    'action': 'create'
                },
                statusCode: self.handleStatusCode,
                success: function (data) {
                    $("#create-item-form")[0].reset();
                    self.createItemForm($(data.form).html());
                    if (data.newItem) {
                        self.newList.push(new PaginatedItem(data.newItem));
                    }
                }
            });
        });
    };

    self.changePage = function (page) {
        page = ko.utils.unwrapObservable(page);
        if (page) {
            $.ajax({
                url: self.utils.formatUrl(page),
                dataType: 'json',
                statusCode: self.handleStatusCode,
                success: function (data) {
                    self.utils.reloadList(data);
                }
            })
        }
    };

    self.updateListLimit = function (model, event) {
        var elem = $(event.currentTarget);
        self.pageLimit(elem.val());
        self.changePage(1);
    };

    self.updateItem = function (paginatedItem, event) {
        var pList = self.paginatedList();
        paginatedItem.dismissModal();
        self.paginatedList(_(pList).without(paginatedItem));
        self.modifiedList.push(paginatedItem);
        $.ajax({
            url: "",
            type: 'post',
            dataType: 'json',
            data: {
                action: 'update'
            },
            statusCode: self.handleStatusCode,
            success: function (data) {
                if (data.error) {
                    self.alertHtml(self.alertHtml() + data.error);
                } else {
                    paginatedItem.handleSuccessfulUpdate(data);
                }
            }
        })
    };
};

var PaginatedItem = function (itemSpec) {
    'use strict';
    var self = this;
    self.itemId = itemSpec.itemData.id;
    self.itemRowId = 'item-row-' + self.itemId;
    self.itemData = ko.observable(itemSpec.itemData);
    self.template = ko.observable(itemSpec.template);

    self.getItemRow = function () {
        return $('#' + self.itemRowId);
    };

    self.dismissModal = function () {
        self.getItemRow().find('.update-item-modal')
            .modal('hide');
    };

    self.handleSuccessfulUpdate = function (data) {
        if (data.template) {
            self.template(data.template);
        }
        if (data.itemData) {
            self.itemData(data.itemData);
        }
    };

    self.initTemplate = function (elems) {
        var $updateButton = $(elems).find('.update-item-confirm');
        if ($updateButton) {
            $updateButton.click(function () {
                $updateButton.button('loading');
                self.getItemRow().trigger('updateItem');
            });
        }
    };
};

ko.bindingHandlers.disabledOnUndefined = {
    update: function(element, valueAccessor) {
        var value = valueAccessor()();
        if (value === undefined) {
            $(element).addClass('disabled');
        } else {
            $(element).removeClass('disabled');
        }
    }
};

ko.bindingHandlers.activeOnSimilar = {
    update: function(element, valueAccessor, allBindingsAccessor) {
        var current = valueAccessor()();
        var compare = parseInt(allBindingsAccessor()['compareText']);
        if (current === compare) {
            $(element).addClass('active');
        } else {
            $(element).removeClass('active');
        }
    }
};
