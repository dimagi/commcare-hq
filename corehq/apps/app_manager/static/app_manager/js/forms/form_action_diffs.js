import _ from 'underscore';


export function getBaseline(formActions) {
    return {
        'open_case': formActions.open_case,
        'update_case': formActions.update_case,
    };
}

export function getDiff(baseline, incoming) {
    const updateDiff = getUpdateDiff(baseline.update_case.update, incoming.update_case.update);
    const diff = {};
    if (Object.keys(updateDiff).length) {
        diff['update_case'] = updateDiff;
    }

    if (incoming.open_case.name_update) {
        const nameDiff = getNameDiff(baseline.open_case.name_update, incoming.open_case.name_update);
        if (nameDiff) {
            diff['open_case'] = nameDiff;
        }
    }

    return diff;
}


function getUpdateDiff(original, incoming) {
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
            const normalizedOriginal = normalizeUpdateObject(original[key]);
            if (!_.isEqual(incoming[key], normalizedOriginal)) {
                updates[key] = {
                    original: normalizedOriginal,
                    updated: incoming[key],
                };
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


function getNameDiff(original, incoming) {
    const normalizedOriginal = normalizeUpdateObject(original);
    if (!_.isEqual(incoming, normalizedOriginal)) {
        return {
            original: normalizedOriginal,
            updated: incoming,
        };
    }

    return null;
}

function normalizeUpdateObject(updateObject) {
    // The server sends the raw data from couch that includes keys not used in our javascript representation.
    // Ideally, the server would strip would these values for us, but because that doesn't happen,
    // remove these extraneous keys here
    return _.omit(updateObject, 'doc_type');
}


export default {
    getBaseline,
    getDiff,
};
