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
        if (nameDiff) {
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
    const normalizedOriginal = {};
    Object.entries(original).forEach(([key, updateList]) => {
        normalizedOriginal[key] = updateList.map(update => normalizeUpdateObject(update));
    });


    allKeys.forEach(key => {
        // If the question is part of the incoming updates, then it is either an addition or an update
        if (!(key in normalizedOriginal)) {
            incoming[key].forEach(update => {
                additions[key] = additions[key] || [];
                additions[key].push(update);
            });
        } else if (key in incoming) {
            incoming[key].forEach(update => {
                const originalMatch = normalizedOriginal[key].find(
                    original => update.question_path === original.question_path);
                if (!originalMatch) {
                    additions[key] = additions[key] || [];
                    additions[key].push(update);
                } else if (originalMatch.update_mode !== update.update_mode) {
                    updates[key] = updates[key] || [];
                    updates[key].push(update);
                }
            });
        }

        // If the question is missing from the incoming updates, then it is a deletion
        if (!(key in incoming)) {
            normalizedOriginal[key].forEach(update => {
                deletions[key] = deletions[key] || [];
                deletions[key].push(update);
            });
        } else if (key in normalizedOriginal) {
            normalizedOriginal[key].forEach(original => {
                if (!incoming[key].find(update => update.question_path === original.question_path)) {
                    deletions[key] = deletions[key] || [];
                    deletions[key].push(original);
                }
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
    let hasResult = false;
    if ('add' in rawDiff) {
        result['add'] = rawDiff['add']['name'];
        hasResult = true;
    }

    if ('delete' in rawDiff) {
        result['delete'] = rawDiff['delete']['name'];
        hasResult = true;
    }

    if ('update' in rawDiff) {
        result['update'] = rawDiff['update']['name'];
        hasResult = true;
    }

    return hasResult ? result : null;
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
