export default (initialValue) => ({
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
});
