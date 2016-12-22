// hqDefine intentionally not used
(function() {
    var InvoiceModel = function () {
        var self = this;
        var invoice = $('#id_do_not_invoice').prop("checked");
        self.noInvoice = ko.observable(invoice);
    };
    
    var invoiceModel = new InvoiceModel();
    // fieldset is not unique enough a css identifier
    // historically this has taken the first one without checking
    // todo: use a more specific identifier to make less brittle
    $('fieldset').first().koApplyBindings(invoiceModel);
}());
