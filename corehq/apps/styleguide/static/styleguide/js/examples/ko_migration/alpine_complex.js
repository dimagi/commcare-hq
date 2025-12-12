import Alpine from 'alpinejs';

Alpine.data('complexExample', (initialValue) => ({
    keyValuePairs: initialValue.map(item => ({
        key: item.key,
        value: item.value,
    })),
    addKeyValuePair() {
        this.keyValuePairs.push({ key: '', value: '' });
    },
    removeKeyValuePair(index) {
        this.keyValuePairs.splice(index, 1);
    },
}));

// If this was its own file, we would also start Alpine here:
// Alpine.start();
