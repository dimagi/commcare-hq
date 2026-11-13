import "commcarehq";

document.getElementById('deactivate-modal').addEventListener('show.bs.modal', e => {
    const btn = e.relatedTarget;
    document.getElementById('deactivate-name').textContent = btn.dataset.endpointName;
    document.getElementById('deactivate-form').action = btn.dataset.deactivateUrl;
});
