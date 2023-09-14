hqDefine("domain/js/billing_statements", [
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'accounting/js/payment_method_handler',
    'hqwebapp/js/bootstrap3/crud_paginated_list',
    'accounting/js/lib/stripe',
], function (
    $,
    _,
    ko,
    initialPageData,
    paymentMethodHandlers,
    CRUDPaginatedList,
    Stripe
) {
    Stripe.setPublishableKey(initialPageData.get("stripe_options").stripe_public_key);
    var wireInvoiceHandler = paymentMethodHandlers.wireInvoiceHandler;
    var paymentMethodHandler = paymentMethodHandlers.paymentMethodHandler;
    var invoice = paymentMethodHandlers.invoice;
    var totalCostItem = paymentMethodHandlers.totalCostItem;
    var pagination = initialPageData.get("pagination");
    var paginatedListModel = new CRUDPaginatedList.CRUDPaginatedListModel(
        pagination.total,
        pagination.limit,
        pagination.page,
        {
            statusCodeText: pagination.status_codes,
            allowItemCreation: initialPageData.get('item_creation_allowed'),
            createItemForm: pagination.create_item_form,
        }
    );

    $(function () {
        $('#editable-paginated-list').koApplyBindings(paginatedListModel);
    });

    var bulkPaymentHandler = paymentMethodHandler(
        "bulk-payment-form",
        {
            submitBtnText: gettext("Submit Payment"),
            errorMessages: initialPageData.get("payment_error_messages"),
            submitURL: initialPageData.get("payment_urls").process_bulk_payment_url,
        }
    );

    var bulkWirePaymentHandler = wireInvoiceHandler(
        "bulk-wire-payment-form",
        {
            submitBtnText: gettext("Submit Invoice Request"),
            isWire: true,
            errorMessages: initialPageData.get("payment_error_messages"),
            submitURL: initialPageData.get("payment_urls").process_wire_invoice_url,
        }
    );

    var paymentHandler = paymentMethodHandler(
        "payment-form",
        {
            submitBtnText: gettext("Submit Payment"),
            errorMessages: initialPageData.get("payment_error_messages"),
            submitURL: initialPageData.get("payment_urls").process_invoice_payment_url,
        }
    );

    // A sign that the data model isn't exactly right - credit cards are shared data.
    // Consider refactoring at some point.
    var handlers = [bulkPaymentHandler, paymentHandler];
    for (var i = 0; i < handlers.length; i++) {
        handlers[i].handlers = handlers;
    }
    var stripeCards = initialPageData.get("stripe_options").stripe_cards;
    if (stripeCards) {
        bulkPaymentHandler.loadCards(stripeCards);
        paymentHandler.loadCards(stripeCards);
    }

    $(function () {
        $('#bulkPaymentModal').koApplyBindings(bulkPaymentHandler);
        $('#bulkWirePaymentModal').koApplyBindings(bulkWirePaymentHandler);
        $('#paymentModal').koApplyBindings(paymentHandler);
    });

    $('#bulkPaymentBtn').click(function () {
        bulkPaymentHandler.costItem(totalCostItem({
            totalBalance: paginatedListModel.totalDue(),
            paginatedListModel: paginatedListModel,
        }));
        bulkPaymentHandler.reset();
    });
    $('#bulkWirePaymentBtn').click(function () {
        bulkWirePaymentHandler.costItem(totalCostItem({
            totalBalance: paginatedListModel.totalDue(),
            paginatedListModel: paginatedListModel,
        }));
    });

    paginatedListModel.totalDue = ko.observable(parseFloat(initialPageData.get("total_balance")));

    paginatedListModel.displayTotalDue = ko.computed(function () {
        return "$" + paginatedListModel.totalDue().toFixed(2);
    });
    paginatedListModel.showUnpaidBills = ko.observable(true);
    paginatedListModel.showAllBills = ko.computed(function () {
        return !paginatedListModel.showUnpaidBills();
    });
    paginatedListModel.toggleUnpaidBills = function () {
        paginatedListModel.showUnpaidBills(!paginatedListModel.showUnpaidBills());
        paginatedListModel.currentPage(1);
        paginatedListModel.refreshList();
    };

    paginatedListModel.getAdditionalData = function () {
        var additionalData = {
            'show_unpaid': paginatedListModel.showUnpaidBills(),
        };
        if (window.location.href.split('?').length > 2) {
            additionalData['show_hidden'] = _(window.location.href.split('?')[1].split('&')).contains('show_hidden=true');
        }
        return additionalData;
    };
    paginatedListModel.initRow = function (rowElems, paginatedItem) {
        var paymentButton = $(rowElems).find('.payment-button');
        if (paymentButton) {
            paymentButton.click(function (e) {
                paymentHandler.costItem(invoice({
                    paginatedItem: paginatedItem,
                    paginatedList: paginatedListModel,
                }));
                paymentHandler.reset();
                e.preventDefault();
            });
        }
    };
    paginatedListModel.init();
});
