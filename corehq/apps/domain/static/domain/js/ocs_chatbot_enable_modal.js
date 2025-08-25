import $ from "jquery";
import { Modal } from 'bootstrap5';

$(function () {
    const modalElement = document.getElementById('ocsChatbotModal');
    const modal = new Modal(modalElement);

    $('#ocs_chatbot_checkbox').on('mousedown', function () {
        if (!this.checked) {
            modal.show();
        }
    });

    modalElement.addEventListener('hidden.bs.modal', function () {
        var tosCheckbox = document.getElementById('tosConfirmation');
        var confirmBtn = document.getElementById('enableOcsChatbotBtn');
        if (tosCheckbox) {
            tosCheckbox.checked = false;
        }
        if (confirmBtn) {
            confirmBtn.disabled = true;
        }
    });

    // Handle TOS confirmation checkbox
    $('#tosConfirmation').on('change', function () {
        var confirmBtn = document.getElementById('enableOcsChatbotBtn');
        if (confirmBtn) {
            confirmBtn.disabled = !this.checked;
        }
    });

    // Handle enable button click
    $('#enableOcsChatbotBtn').on('click', function () {
        var tosCheckbox = document.getElementById('tosConfirmation');
        if (tosCheckbox && tosCheckbox.checked) {
            $('#ocs_chatbot_checkbox').prop('checked', true);
            modal.hide();
        }
    });
});