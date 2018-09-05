hqDefine("domain/js/billing_statements", [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'accounting/js/payment_method_handler',
    'hqwebapp/js/crud_paginated_list',
    'stripe',
], function(
    $,
    ko,
    initialPageData,
    paymentMethodHandlers,
    CRUDPaginatedList,
    Stripe
) {
    Stripe.setPublishableKey(initialPageData.get("stripe_options").stripe_public_key);
    var WireInvoiceHandler = paymentMethodHandlers.WireInvoiceHandler;
    var PaymentMethodHandler = paymentMethodHandlers.PaymentMethodHandler;
    var Invoice = paymentMethodHandlers.Invoice;
    var TotalCostItem = paymentMethodHandlers.TotalCostItem;
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

    var bulkPaymentHandler = new PaymentMethodHandler(
        "bulk-payment-form",
        {
            submitBtnText: gettext("Submit Payment"),
            errorMessages: initialPageData.get("payment_error_messages"),
            submitURL: initialPageData.get("payment_urls").process_bulk_payment_url,
        }
    );

    var bulkWirePaymentHandler = new WireInvoiceHandler(
        "bulk-wire-payment-form",
        {
            submitBtnText: gettext("Submit Invoice Request"),
            isWire: true,
            errorMessages: initialPageData.get("payment_error_messages"),
            submitURL: initialPageData.get("payment_urls").process_wire_invoice_url,
        }
    );

    var paymentHandler = new PaymentMethodHandler(
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
    var stripe_cards = initialPageData.get("stripe_options").stripe_cards;
    if (stripe_cards) {
        bulkPaymentHandler.loadCards(stripe_cards);
        paymentHandler.loadCards(stripe_cards);
    }

    $(function () {
        $('#bulkPaymentModal').koApplyBindings(bulkPaymentHandler);
        $('#bulkWirePaymentModal').koApplyBindings(bulkWirePaymentHandler);
        $('#paymentModal').koApplyBindings(paymentHandler);
    });

    $('#bulkPaymentBtn').click(function () {
        bulkPaymentHandler.costItem(new TotalCostItem({
            totalBalance: paginatedListModel.totalDue(),
            paginatedListModel: paginatedListModel,
        }));
        bulkPaymentHandler.reset();
    });
    $('#bulkWirePaymentBtn').click(function () {
        bulkWirePaymentHandler.costItem(new TotalCostItem({
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
        var additional_data = {
            'show_unpaid': paginatedListModel.showUnpaidBills(),
        };
        if (window.location.href.split('?').length > 2) {
            additional_data['show_hidden'] = _(window.location.href.split('?')[1].split('&')).contains('show_hidden=true');
        }
        return additional_data;
    };
    paginatedListModel.initRow = function (rowElems, paginatedItem) {
        var paymentButton = $(rowElems).find('.payment-button');
        if (paymentButton) {
            paymentButton.click(function (e) {
                paymentHandler.costItem(new Invoice({
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
