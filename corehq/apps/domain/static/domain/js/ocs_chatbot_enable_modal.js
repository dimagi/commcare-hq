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
            $('#ocs_chatbot_checkbox').prop('checked', true);
            $('#ocsChatbotModal').modal('hide');
        }
    };

    self.resetModal = function () {
        self.isTosConfirmed(false);
    };
}

$(function () {
    const viewModel = new ToSModalViewModel();

    ko.applyBindings(viewModel, document.getElementById('ocsChatbotModal'));

    const checkbox = $('#ocs_chatbot_checkbox');
    viewModel.isChatbotEnabled(checkbox.prop('checked'));

    $('#ocsChatbotModal').on('hidden.bs.modal', function () {
        viewModel.resetModal();
    });

    $('#ocs_chatbot_checkbox').on('mousedown', function () {
        if (!this.checked) {
            $('#ocsChatbotModal').modal('show');
        }
    });
});
