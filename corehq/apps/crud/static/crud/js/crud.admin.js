/***
 * THIS IS DEPRECATED. PLEASE DON'T USE THIS. THE ONLY THING THAT USES THIS
 * IS THE MVP INDICATOR ADMIN INTERFACE. THIS IS SO TERRIBLE.
 * -- Biyeun
 */

var CRUDAdminControl = function(options) {
    var self = this;
    self.actionButton = $('<a href="#crud_add_modal" class="btn btn-primary" ' +
        'data-toggle="modal" style="margin-left:2px" />').html('<i class="fa fa-plus"/> ').append(
        "Add New "+options.itemType);
    self.formSubmitPath = options.formSubmitPath;
    self.formType = options.formType;
    self.formSubmitURL = self.formSubmitPath+self.formType+'/';
    self.hideButton = options.hideButton;
    self.newFormSubmitURL = self.formSubmitURL+'new/';
    self.updateFormSubmitURL = self.formSubmitURL+'update/';
    self.overrideNewFormType = null;
    self.overrideNewFormDiv = '#crud_add_modal .modal-body';

    var refreshForm = function(modal, data, formBodyDiv) {
        var prepend = "";
        $(formBodyDiv).html(data.form_update).prepend(prepend);
        modal.find('form button[type="submit"]').button('reset');
        if (data.success)
            modal.modal('hide');
    },
    updateRow = function (rowElem, rowData) {
        $('.datatable tbody tr').removeClass('active');
        $.each($(rowElem).children(), function (ind) {
            $(this).html(rowData[ind]);
        });
        $(rowElem).addClass('active');
    },
    overrideFormTypeInUrl = function (url, form_type) {
        if (form_type)
            url = url.replace(self.formType, form_type);
        return url;
    },
    resetSubmitButton = function (data) {
        $('button[type="submit"]').button('reset');
    };

    self.init = function () {
        $(function() {
            if(!self.hideButton) {
                $('#reportFiltersAccordion .row .col-xs-8').append(self.actionButton);
            }
            self.actionButton.click(function () {
                $('#js-add-crud-success').addClass('hide');
            });
            self.addItemModal = $('#crud_add_modal');
            self.updateItemModal = $('#crud_update_modal');

            self.init_new_form();

            $('#crud_add_modal form').submit(function (e) {
                var $submitBtn = $('#js-crud-add-submit');
                if (! $submitBtn.hasClass('disabled')) {
                    $submitBtn.button('loading');
                    $(this).ajaxSubmit({
                        method: 'POST',
                        url: overrideFormTypeInUrl(self.newFormSubmitURL, self.overrideNewFormType),
                        success: function (data) {
                            self.refreshAddItemForm(data);
                            reportTables.datatable.fnAddData(data.rows);
                            $('#js-add-crud-success').removeClass('hide');
                        },
                        error: resetSubmitButton,
                            dataType: 'json'
                    });
                }
                e.preventDefault();
                return false;
            });

            $('#crud_update_modal button').click(function (e) {
                var submit_url = self.updateFormSubmitURL;
                if ($(this).hasClass('btn-danger')) {
                    submit_url = self.formSubmitURL+'delete/';
                }
                self.updateItemModal.find('input[disabled="disabled"]').removeProp('disabled');

                self.updateItemModal.find('form').ajaxSubmit({
                    dataType: 'json',
                    url: overrideFormTypeInUrl(submit_url, self.currentItemFormType)+self.currentItemID+'/',
                    success: self.refreshUpdateItemForm,
                    error: resetSubmitButton
                });
                e.preventDefault();
                return false;
            });

        });
    };

    self.init_new_form = function () {
        $.ajax({
            dataType: 'json',
            url: overrideFormTypeInUrl(self.newFormSubmitURL, self.overrideNewFormType),
            method: 'GET',
            success: self.refreshAddItemForm,
            error: resetSubmitButton
        });
    };

    self.update_item = function(button) {
        self.currentItemID = $(button).data('item_id');
        self.currentItemFormType = $(button).data('form_class');
        $.ajax({
            dataType: 'json',
            url: overrideFormTypeInUrl(self.updateFormSubmitURL, self.currentItemFormType)+self.currentItemID+'/',
            method: 'GET',
            success: self.refreshUpdateItemForm,
            error: resetSubmitButton
        });
    };

    self.refreshAddItemForm = function(data) {
        refreshForm(self.addItemModal, data, self.overrideNewFormDiv);
    };

    self.refreshUpdateItemForm = function(data) {
        var row = $('[data-item_id="'+self.currentItemID+'"]').parent().parent()[0];
        if (data.deleted)
            reportTables.datatable.fnDeleteRow(reportTables.datatable.fnGetPosition(row));
        if (data.success && !data.deleted && data.rows)
            updateRow(row, data.rows[0]);
        refreshForm(self.updateItemModal, data, '#crud_update_modal .modal-body');
    };

};
