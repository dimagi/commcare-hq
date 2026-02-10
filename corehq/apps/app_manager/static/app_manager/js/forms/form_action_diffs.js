import _ from 'underscore';


export function getBaseline(formActions) {
    return {
        'open_case': formActions.open_case,
        'update_case': formActions.update_case,
    };
}

export function getDiff(baseline, incoming) {
    const updateDiff = getUpdateMultiDiff(baseline.update_case.update_multi, incoming.update_case.update_multi);
    const diff = {};
    if (Object.keys(updateDiff).length) {
        diff['update_case'] = updateDiff;
    }

    if (incoming.open_case.name_update_multi) {
        const nameDiff = getNameDiff(baseline.open_case.name_update_multi, incoming.open_case.name_update_multi);
        if (Object.keys(nameDiff).length) {
            diff['open_case'] = nameDiff;
        }
    }

    return diff;
}

function getUpdateMultiDiff(original, incoming) {
    const additions = {};
    const deletions = {};
    const updates = {};

    const allKeys = new Set([...Object.keys(original), ...Object.keys(incoming)]);
    const baseline = Object.fromEntries(Object.entries(original).map(([key, items]) => {
        [key, items.map(omitDocType)];
    }));

    allKeys.forEach(key => {
        if (Object.hasOwn(baseline, key) && Object.hasOwn(incoming, key)) {
            incoming[key].forEach(item => {
                const match = baseline[key].find(q => q.question_path === item.question_path);
                if (!match) {
                    additions[key] = additions[key] || [];
                    additions[key].push(item);
                } else if (match.update_mode !== item.update_mode) {
                    updates[key] = updates[key] || [];
                    updates[key].push(item);
                }
            });
            baseline[key].forEach(item => {
                if (!incoming[key].find(q => q.question_path === item.question_path)) {
                    deletions[key] = deletions[key] || [];
                    deletions[key].push(item);
                }
            });
        } else if (Object.hasOwn(incoming, key)) {  // not in baseline
            incoming[key].forEach(item => {
                additions[key] = additions[key] || [];
                additions[key].push(item);
            });
        } else {  // key in baseline, not in incoming
            baseline[key].forEach(item => {
                deletions[key] = deletions[key] || [];
                deletions[key].push(item);
            });
        }
    });

    let diff = {};
    if (Object.keys(additions).length) {
        diff['add'] = additions;
    }
    if (Object.keys(deletions).length) {
        diff['delete'] = deletions;
    }
    if (Object.keys(updates).length) {
        diff['update'] = updates;
    }
    return diff;
}

function getNameDiff(original, updated) {
    const normalizedOriginal = {'name': original};
    const normalizedUpdated = {'name': updated};
    const rawDiff = getUpdateMultiDiff(normalizedOriginal, normalizedUpdated);

    const result = {};
    if ('add' in rawDiff) {
        result['add'] = rawDiff['add']['name'];
    }

    if ('delete' in rawDiff) {
        result['delete'] = rawDiff['delete']['name'];
    }

    if ('update' in rawDiff) {
        result['update'] = rawDiff['update']['name'];
    }

    return result;
}

function omitDocType(updateObject) {
    // The server sends the raw data from couch that includes keys not used in our javascript representation.
    // Ideally, the server would strip would these values for us, but because that doesn't happen,
    // remove these extraneous keys here
    return _.omit(updateObject, 'doc_type');
}


export default {
    getBaseline,
    getDiff,
};
