/***
 * THIS IS DEPRECATED. PLEASE DON'T USE THIS. THE ONLY THING THAT USES THIS
 * IS THE MVP INDICATOR ADMIN INTERFACE. THIS IS SO TERRIBLE.
 * -- Biyeun
 */
hqDefine("crud/js/admin", function () {
    var CRUDAdminControl = function (options) {
        var self = {};
        self.actionButton = $('<a href="#crud_add_modal" class="btn btn-primary" ' +
            'data-toggle="modal" style="margin-left:2px" />').html('<i class="fa fa-plus"/> ').append(
            "Add New " + options.itemType);
        self.formSubmitPath = options.formSubmitPath;
        self.formType = options.formType;
        self.slug = options.slug;
        self.formSubmitURL = self.formSubmitPath + self.formType + '/';
        self.newFormSubmitURL = self.formSubmitURL + 'new/';
        self.updateFormSubmitURL = self.formSubmitURL + 'update/';
        self.overrideNewFormType = null;
        self.overrideNewFormDiv = '#crud_add_modal .modal-body';

        var refreshForm = function (modal, data, formBodyDiv) {
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
            overrideFormTypeInUrl = function (url, formType) {
                if (formType) {
                    url = url.replace(self.formType, formType);
                }
                return url;
            },
            resetSubmitButton = function () {
                $('button[type="submit"]').button('reset');
            };

        self.datatable = function () {
            var selector = $('#report_table_' + self.slug + '.datatable');
            if (!$(selector).length) {
                throw new Error("Could not find datatable " + selector);
            }
            return $(selector).dataTable();
        };

        self.init = function () {
            $('#reportFiltersAccordion .row .col-xs-8').append(self.actionButton);
            self.addItemModal = $('#crud_add_modal');
            self.updateItemModal = $('#crud_update_modal');

            self.init_new_form();

            $('#crud_add_modal form').submit(function (e) {
                var $submitBtn = $('#js-crud-add-submit');
                if (!$submitBtn.hasClass('disabled')) {
                    $submitBtn.button('loading');
                    $(this).ajaxSubmit({
                        method: 'POST',
                        url: overrideFormTypeInUrl(self.newFormSubmitURL, self.overrideNewFormType),
                        success: function (data) {
                            self.refreshAddItemForm(data);
                            self.datatable().fnAddData(data.rows);
                            hqImport("hqwebapp/js/alert_user").alert_user(gettext("Indicator added to end of table"), "success");
                        },
                        error: resetSubmitButton,
                        dataType: 'json',
                    });
                }
                e.preventDefault();
                return false;
            });

            $('#crud_update_modal button').click(function (e) {
                var submitUrl = self.updateFormSubmitURL;
                if ($(this).hasClass('btn-danger')) {
                    submitUrl = self.formSubmitURL + 'delete/';
                }
                self.updateItemModal.find('input[disabled="disabled"]').removeProp('disabled');

                self.updateItemModal.find('form').ajaxSubmit({
                    dataType: 'json',
                    url: overrideFormTypeInUrl(submitUrl, self.currentItemFormType) + self.currentItemID + '/',
                    success: self.refreshUpdateItemForm,
                    error: resetSubmitButton,
                });
                e.preventDefault();
                return false;
            });
        };

        self.init_new_form = function () {
            $.ajax({
                dataType: 'json',
                url: overrideFormTypeInUrl(self.newFormSubmitURL, self.overrideNewFormType),
                method: 'GET',
                success: self.refreshAddItemForm,
                error: resetSubmitButton,
            });
        };

        self.update_item = function (button) {
            self.currentItemID = $(button).data('item_id');
            self.currentItemFormType = $(button).data('form_class');
            $.ajax({
                dataType: 'json',
                url: overrideFormTypeInUrl(self.updateFormSubmitURL, self.currentItemFormType) + self.currentItemID + '/',
                method: 'GET',
                success: self.refreshUpdateItemForm,
                error: resetSubmitButton,
            });
        };

        self.refreshAddItemForm = function (data) {
            refreshForm(self.addItemModal, data, self.overrideNewFormDiv);
        };

        self.refreshUpdateItemForm = function (data) {
            var row = $('[data-item_id="' + self.currentItemID + '"]').parent().parent()[0];
            if (data.deleted)
                self.datatable().fnDeleteRow(self.datatable().fnGetPosition(row));
            if (data.success && !data.deleted && data.rows)
                updateRow(row, data.rows[0]);
            refreshForm(self.updateItemModal, data, '#crud_update_modal .modal-body');
        };

        return self;
    };

    var initialPageData = hqImport("hqwebapp/js/initial_page_data").get;
    $(document).on('ajaxSuccess', function (e, xhr, ajaxOptions) {
        var jsOptions = initialPageData("js_options");
        if (jsOptions && ajaxOptions.url.indexOf(jsOptions.asyncUrl) === -1) {
            return;
        }

        // CRUD pages will have supplied a crud_item
        var crudItem = (initialPageData("js_options") || {}).crud_item;
        if (!crudItem) {
            return;
        }

        var crudInterface = CRUDAdminControl({
            itemType: crudItem.type,
            formSubmitPath: crudItem.url,
            formType: crudItem.form,
            slug: jsOptions.slug,
        });
        crudInterface.init();

        $(".crud-edit").click(function (e) {
            crudInterface.update_item(e.currentTarget);
        });
        $(".form-label").tooltip();

        // Add bulk copy button
        var $filters = $("#reportFiltersAccordion");
        if (!$filters.find("a.bulk-add").length) {
            var content = '  <a href="' + crudItem.bulk_add_url + '" class="btn btn-primary"><i class="fa fa-copy"></i> Copy Indicators to another Project</a>';
            $filters.find('.row .col-xs-8').append(content);
        }

        // Add couch doc input behavior
        var $changeDocType = $('#id_change_doc_type');
        if ($changeDocType) {
            $('#id_doc_type_choices').parent().parent().hide();
            $('#id_change_doc_type').prop('checked', false);
            $changeDocType.change(function () {
                var $docType = $('#id_doc_type_choices').parent().parent();
                ($(this).prop('checked')) ? $docType.fadeIn() : $docType.fadeOut();
            });
        }
    });
});
