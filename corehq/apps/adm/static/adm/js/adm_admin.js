var ADMAdminControl = function(options) {
    var self = this;
    self.actionButton = $('<a href="#addADMItemModal" class="btn btn-primary" data-toggle="modal" style="margin-left:2px" />').html('<i class="icon-white icon-plus"/> ').append("Add New "+options.itemType);
    self.formSubmitPath = options.formSubmitPath;
    self.formType = options.formType;
    self.formSubmitURL = self.formSubmitPath+self.formType+'/';
    self.newFormSubmitURL = self.formSubmitURL+'new/';
    self.updateFormSubmitURL = self.formSubmitURL+'update/';
    self.overrideNewFormType = null;
    self.overrideNewFormDiv = null;

    var refreshForm = function(modal, data, formBodyDiv) {
            var prepend = "";
            if (!formBodyDiv) {
                formBodyDiv = modal.find('form .modal-body');
                if(self.currentItemFormType)
                    prepend = '<div class="control-group">' +
                        '<label class="control-label">Column Type</label>' +
                        '<div class="controls"><span class="label label-inverse">'+
                        self.currentItemFormType.replace('Form','')+
                        '</span></div></div>';
            }
            formBodyDiv.html(data.form_update).prepend(prepend);
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
            $('#reportFiltersAccordion .accordion-actions').append(self.actionButton);
            self.addADMItemModal = $('#addADMItemModal');
            self.updateADMItemModal = $('#updateADMItemModal');

            self.init_new_form();

            self.addADMItemModal.find('form').submit(function () {
                if (! $(this).find('button[type="submit"]').hasClass('disabled')) {
                    $(this).find('button[type="submit"]').button('loading');
                    $(this).ajaxSubmit({
                        method: 'POST',
                        url: overrideFormTypeInUrl(self.newFormSubmitURL, self.overrideNewFormType),
                        success: self.refreshAddADMItemForm,
                        error: resetSubmitButton,
                        dataType: 'json'
                    });
                }
                return false;
            });

            self.updateADMItemModal.find('form .modal-footer button[type="submit"]').click(function () {
                var submit_url = self.updateFormSubmitURL;
                if ($(this).hasClass('btn-danger')) {
                    submit_url = self.formSubmitURL+'delete/';
                }

                self.updateADMItemModal.find('form').ajaxSubmit({
                    dataType: 'json',
                    url: overrideFormTypeInUrl(submit_url, self.currentItemFormType)+self.currentItemID+'/',
                    success: self.refreshUpdateADMItemForm,
                    error: resetSubmitButton
                });
                return false;
            });

        });
    };

    self.init_new_form = function () {
        $.ajax({
            dataType: 'json',
            url: overrideFormTypeInUrl(self.newFormSubmitURL, self.overrideNewFormType),
            method: 'GET',
            success: self.refreshAddADMItemForm,
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
            success: self.refreshUpdateADMItemForm,
            error: resetSubmitButton
        })
    };

    self.refreshAddADMItemForm = function(data) {
        refreshForm(self.addADMItemModal, data, self.overrideNewFormDiv);
        reportTables.datatable.fnAddData(data.rows);

    };
    self.refreshUpdateADMItemForm = function(data) {
        var row = $('[data-item_id="'+self.currentItemID+'"]').parent().parent()[0];
        if (data.deleted)
            reportTables.datatable.fnDeleteRow(reportTables.datatable.fnGetPosition(row));
        if (data.success && !data.deleted && data.rows)
            updateRow(row, data.rows[0]);

        refreshForm(self.updateADMItemModal, data, null);
    };

};