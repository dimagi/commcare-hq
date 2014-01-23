var CRUDAdminControl = function(options) {
    var self = this;
    self.actionButton = $('<a href="#crud_add_modal" class="btn btn-primary" ' +
        'data-toggle="modal" style="margin-left:2px" />').html('<i class="icon-white icon-plus"/> ').append(
        "Add New "+options.itemType);
    self.formSubmitPath = options.formSubmitPath;
    self.formType = options.formType;
    self.formSubmitURL = self.formSubmitPath+self.formType+'/';
    self.hideButton = options.hideButton;
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
        },
        check_modal_height = function (modal) {
            var win_height = $(window).height();
            modal.css('top', '10px').css('margin-top', '0px');
            modal.find('.modal-body').css('max-height', win_height-180+"px");
        };

    self.init = function () {
        $(function() {
            if(!self.hideButton) {
                $('#reportFiltersAccordion .accordion-actions').append(self.actionButton);
            }
            self.addItemModal = $('#crud_add_modal');
            self.updateItemModal = $('#crud_update_modal');

            self.addItemModal.on('show', function () {
                check_modal_height($(this));
            });
            self.updateItemModal.on('show', function () {
                check_modal_height($(this));
            });

            self.init_new_form();

            self.addItemModal.find('form').submit(function () {
                if (! $(this).find('button[type="submit"]').hasClass('disabled')) {
                    $(this).find('button[type="submit"]').button('loading');
                    $(this).ajaxSubmit({
                        method: 'POST',
                        url: overrideFormTypeInUrl(self.newFormSubmitURL, self.overrideNewFormType),
                        success: self.refreshAddItemForm,
                        error: resetSubmitButton,
                        dataType: 'json'
                    });
                }
                return false;
            });

            self.updateItemModal.find('form .modal-footer button[type="submit"]').click(function () {
                var submit_url = self.updateFormSubmitURL;
                if ($(this).hasClass('btn-danger')) {
                    submit_url = self.formSubmitURL+'delete/';
                }
                self.updateItemModal.find('input[disabled="disabled"]').removeAttr('disabled');

                self.updateItemModal.find('form').ajaxSubmit({
                    dataType: 'json',
                    url: overrideFormTypeInUrl(submit_url, self.currentItemFormType)+self.currentItemID+'/',
                    success: self.refreshUpdateItemForm,
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
        })
    };

    self.refreshAddItemForm = function(data) {
        refreshForm(self.addItemModal, data, self.overrideNewFormDiv);
        reportTables.datatable.fnAddData(data.rows);

    };
    self.refreshUpdateItemForm = function(data) {
        var row = $('[data-item_id="'+self.currentItemID+'"]').parent().parent()[0];
        if (data.deleted)
            reportTables.datatable.fnDeleteRow(reportTables.datatable.fnGetPosition(row));
        if (data.success && !data.deleted && data.rows)
            updateRow(row, data.rows[0]);

        refreshForm(self.updateItemModal, data, null);
    };

};
