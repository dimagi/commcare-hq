import "commcarehq";
import $ from "jquery";
import ko from 'knockout';
import "hqwebapp/js/bootstrap5/knockout_bindings.ko";

function ToSModalViewModel() {
    const self = this;

    self.isTosConfirmed = ko.observable(false);
    self.isChatbotEnabled = ko.observable(false);

    self.isEnableButtonEnabled = ko.computed(() => {
        return self.isTosConfirmed();
    });

    self.enableChatbot = function () {
        if (self.isTosConfirmed()) {
            self.isChatbotEnabled(true);
            $('#ocs_chatbot_checkbox').prop('checked', true).trigger('change');
            $('#ocs-chatbot-modal').modal('hide');
        }
    };

    self.resetModal = function () {
        self.isTosConfirmed(false);
    };
}

function initModalBindings() {
    const viewModel = new ToSModalViewModel();

    ko.applyBindings(viewModel, document.getElementById('ocs-chatbot-modal'));

    const checkbox = $('#ocs_chatbot_checkbox');
    viewModel.isChatbotEnabled(checkbox.prop('checked'));

    $('#ocs-chatbot-modal').on('hidden.bs.modal', function () {
        viewModel.resetModal();
    });

    $('#ocs_chatbot_checkbox').on('mousedown', function () {
        if (!this.checked) {
            $('#ocs-chatbot-modal').modal('show');
        }
    });
}

function trackChanges() {
    var unsavedChanges = false;
    var initialStates = {};

    // Store initial checkbox states
    $("#feature-previews-form input[type='checkbox']").each(function () {
        initialStates[$(this).attr('name')] = $(this).is(':checked');
    });

    $("#feature-previews-form input[type='checkbox']").on('change', function () {
        unsavedChanges = true;
    });

    $(window).on('beforeunload', function () {
        if (unsavedChanges) {
            var hasChanges = false;
            $("#feature-previews-form input[type='checkbox']").each(function () {
                if ($(this).is(':checked') !== initialStates[$(this).attr('name')]) {
                    hasChanges = true;
                }
            });

            if (hasChanges) {
                return true;
            }
        }
    });

    $("#feature-previews-form").on('submit', function () {
        $(window).off("beforeunload");
    });
}

$(function () {
    initModalBindings();
    trackChanges();
});
