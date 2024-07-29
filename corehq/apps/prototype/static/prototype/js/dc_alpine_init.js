// todo: this should move into the Webpack module once alpine is properly bundled

document.addEventListener('alpine:init', () => {
    Alpine.store('whitespaces', {
        show: false,
    });
});
