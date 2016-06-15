// hqDefine intentionally not used
(function() {
    var InvoiceModel = function () {
        var self = this;
        var invoice = $('#id_do_not_invoice').attr("checked");
        self.noInvoice = ko.observable(invoice);
    };
    
    var invoiceModel = new InvoiceModel();
    $('fieldset').koApplyBindings(invoiceModel);
}());
