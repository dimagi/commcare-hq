import _ from 'underscore';

export function getDiff(original, incoming) {
    const additions = {};
    const deletions = [];
    const updates = {};

    const allKeys = new Set([...Object.keys(original), ...Object.keys(incoming)]);
    allKeys.forEach(key => {
        if (!(key in original)) {
            additions[key] = incoming[key];
        } else if (!(key in incoming)) {
            deletions.push(key);
        } else {
            // The server sends the raw data from couch. Ideally, the client would never have to deal with
            // extraneous keys like 'doc_type', so remove them to make comparison simple
            const normalizedOriginal = _.omit(original[key], 'doc_type');
            if (!_.isEqual(incoming[key], normalizedOriginal)) {
                updates[key] = incoming[key];
            }
        }
    });

    let diff = {};
    if (Object.keys(additions).length) {
        diff['add'] = additions;
    }

    if (Object.keys(updates).length) {
        diff['update'] = updates;
    }

    if (deletions.length) {
        diff['del'] = deletions;
    }

    return diff;
}

export default {
    getDiff,
};