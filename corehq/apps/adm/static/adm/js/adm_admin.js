var ADMAdminControl = function(options) {
    var self = this;
    self.actionButton = $('<a href="#addADMItemModal" class="btn btn-primary" data-toggle="modal" style="margin-left:2px" />').html('<i class="icon-white icon-plus"/> ').append("Add New "+options.itemType);
    self.formSubmitURL = options.formSubmitURL;
    self.newFormSubmitURL = self.formSubmitURL+'new/';
    self.updateFormSubmitURL = self.formSubmitURL+'update/';

    var refreshForm = function(modal, data) {
            modal.find('form .modal-body').html(data.form_update);
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
        };

    self.init = function () {
        $(function() {
            $('#reportFiltersAccordion .accordion-actions').append(self.actionButton);
            self.addADMItemModal = $('#addADMItemModal');
            self.updateADMItemModal = $('#updateADMItemModal');

            $.ajax({
                dataType: 'json',
                url: self.newFormSubmitURL,
                method: 'GET',
                success: refreshAddADMItemForm
            });

            self.addADMItemModal.find('form').submit(function () {
                $(this).find('button[type="submit"]').button('loading');
                $(this).ajaxSubmit({
                    method: 'POST',
                    url: self.newFormSubmitURL,
                    success: refreshAddADMItemForm,
                    dataType: 'json'
                });
                return false;
            });

            self.updateADMItemModal.find('form .modal-footer button[type="submit"]').click(function () {
                var submit_url = self.updateFormSubmitURL;
                if ($(this).hasClass('btn-danger')) {
                    submit_url = self.formSubmitURL+'delete/';
                }

                self.updateADMItemModal.find('form').ajaxSubmit({
                    dataType: 'json',
                    url: submit_url+self.currentItemID+'/',
                    success: refreshUpdateADMItemForm
                });
                return false;
            });

        });
    };

    self.update_item = function(button) {
        console.log(button);
        self.currentItemID = $(button).data('item_id');
        console.log(self.currentItemID);
        $.ajax({
            dataType: 'json',
            url: self.updateFormSubmitURL+self.currentItemID+'/',
            method: 'GET',
            success: refreshUpdateADMItemForm
        })
    };

    var refreshAddADMItemForm = function(data) {
            console.log(data);
            refreshForm(self.addADMItemModal, data);
            reportTables.datatable.fnAddData(data.rows);

        },
        refreshUpdateADMItemForm = function(data) {
            console.log(data);
            var row = $('[data-item_id="'+self.currentItemID+'"]').parent().parent()[0];
            if (data.deleted)
                reportTables.datatable.fnDeleteRow(reportTables.datatable.fnGetPosition(row));
            if (data.success && !data.deleted && data.rows)
                updateRow(row, data.rows[0]);

            refreshForm(self.updateADMItemModal, data);
        };

};