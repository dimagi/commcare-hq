import $ from "jquery";

/**
 * Handler function for selection of multiple checkbox inputs. Accepts a callback function executed on selection
 and selected rows ids passed as a parameter.
 *
 * @param {string} selectRowInputName - The name of checkbox input element for the row
 * @param {string} selectAllInputName - The name of checkbox input element for selection of all rows
 * @param {Object} callbackFnOnSelection - Callback function that is executed on selection
 */
function multiCheckboxSelectionHandler(selectRowInputName, selectAllInputName, callbackFnOnSelection = null) {
    var self = this;
    self.selectedIds = [];

    self.init = function () {
        $(document).on('change', `input[name="${selectRowInputName}"]`, handleRowSelection);
        $(document).on('change', `input[name="${selectAllInputName}"]`, handleSelectAll);
    };

    const handleRowSelection = function (event) {
        const rowId = $(event.target).val();
        const isChecked = $(event.target).prop('checked');

        if (isChecked) {
            self.selectedIds.push(rowId);
        } else {
            self.selectedIds = self.selectedIds.filter(id => id !== rowId);
        }

        if (callbackFnOnSelection) {
            callbackFnOnSelection(self.selectedIds);
        }
        updateSelectAllCheckbox();
    };

    const handleSelectAll = function (event) {
        const isChecked = $(event.target).prop('checked');
        const $rowCheckboxes = $(`input[name="${selectRowInputName}"]:not(:disabled)`);

        $rowCheckboxes.prop('checked', isChecked);
        if (isChecked) {
            self.selectedIds = $rowCheckboxes.map(function () {
                return $(this).val();
            }).get();
        } else {
            self.selectedIds = [];
        }

        if (callbackFnOnSelection) {
            callbackFnOnSelection(self.selectedIds);
        }
    };

    const updateSelectAllCheckbox = function () {
        const $selectAll = $(`input[name="${selectAllInputName}"]`);
        if (self.selectedIds.length === 0) {
            $selectAll.prop('checked', false);
        }
    };
}


export {
    multiCheckboxSelectionHandler,
};
