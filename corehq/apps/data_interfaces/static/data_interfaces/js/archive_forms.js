hqDefine("data_interfaces/js/archive_forms", function () {
    var managementSelector = '#data-interfaces-archive-forms',
        allFormsButtonSelector = managementSelector + ' input[name="select_all"]',
        checkboxesSelector = managementSelector + ' input.xform-checkbox',
        indicatorSelector = '#count_indicator';

    function updateFormCounts() {
        var selectedCount = $(managementSelector + ' input.xform-checkbox:checked').length;
        $(".selectedCount").text(selectedCount);
        toggleButton(selectedCount);
    }

    function toggleButton(count) {
        if (count) {
            $("#submitForms").prop('disabled', false);
        } else {
            $("#submitForms").prop('disabled', true);
        }
    }

    function selectNone() {
        $(managementSelector + ' input.xform-checkbox:checked').prop('checked', false).change();
        $(allFormsButtonSelector).prop('checked', false);
    }

    // Similar to case_management.js, would be good to combine the two
    $(function () {
        // bindings for 'all' button
        $(document).on('click', managementSelector + ' a.select-visible', function () {
            $(allFormsButtonSelector).prop('checked', false);
            $(checkboxesSelector).prop('checked', true).change();
            return false;
        });

        // bindings for 'none' button
        $(document).on('click', managementSelector + ' a.select-none', function () {
            selectNone();
            return false;
        });

        // bindings for form checkboxes
        $(document).on('change', checkboxesSelector, function () {
            // updates text like '3 of 5 selected'
            updateFormCounts();
            $(indicatorSelector).show();
        });
        $(document).on('click', checkboxesSelector, function () {
            $(allFormsButtonSelector).prop('checked', false);
        });

        // bindings for 'Select all' checkboxes
        $(document).on('click', allFormsButtonSelector, function () {
            if (this.checked) {
                $(checkboxesSelector).prop('checked', true).change();
                $(indicatorSelector).hide();
                toggleButton(1);
            } else {
                $(indicatorSelector).show();
                $(".selectedCount").text(0);
                $(managementSelector + ' a.select-none').click();
                toggleButton(0);
            }
        });

        // clear checkboxes when changing page
        $(document).on('mouseup', managementSelector + ' .dataTables_paginate a', selectNone);
        $(document).on('change', managementSelector + ' .dataTables_length select', selectNone);

        $(document).on('click', '#submitForms', function () {
            if ($(allFormsButtonSelector)[0].checked) {
                hqImport('analytix/js/google').track.event('Bulk Archive', 'All', 'Checkbox');
            } else {
                hqImport('analytix/js/google').track.event('Bulk Archive', 'All', 'Selected Forms');
            }
        });
    });
});
