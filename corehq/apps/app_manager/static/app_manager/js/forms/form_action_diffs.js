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
        diff['update_case_multi'] = updateDiff;
    }

    if (incoming.open_case.name_update) {
        const nameDiff = getNameDiff(baseline.open_case.name_update, incoming.open_case.name_update);
        if (nameDiff) {
            diff['open_case'] = nameDiff;
        }
    }

    return diff;
}

function getUpdateMultiDiff(original, incoming) {
    const additions = {};
    const deletions = {};

    const allKeys = new Set([...Object.keys(original), ...Object.keys(incoming)]);
    const normalizedOriginal = {};
    Object.entries(original).forEach(([key, updateList]) => {
        normalizedOriginal[key] = updateList.map(update => normalizeUpdateObject(update));
    });


    allKeys.forEach(key => {
        if (!(key in normalizedOriginal)) {
            incoming[key].forEach(update => {
                additions[key] = additions[key] || [];
                additions[key].push(update);
            });
        } else if (key in incoming) {
            incoming[key].forEach(update => {
                if (!normalizedOriginal[key].find(ele => _.isEqual(update, ele))) {
                    additions[key] = additions[key] || [];
                    additions[key].push(update);
                }
            });
        }

        if (!(key in incoming)) {
            normalizedOriginal[key].forEach(update => {
                deletions[key] = deletions[key] || [];
                deletions[key].push(update);
            });
        } else if (key in normalizedOriginal) {
            normalizedOriginal[key].forEach(update => {
                if (!incoming[key].find(ele => _.isEqual(update, ele))) {
                    deletions[key] = deletions[key] || [];
                    deletions[key].push(update);
                }
            });
        }
    });

    let diff = {};
    if (Object.keys(additions).length) {
        diff['add'] = additions;
    }

    if (Object.keys(deletions).length) {
        diff['del'] = deletions;
    }

    return diff;
}

// TODO: Handle update multi for name diffs, too
function getNameDiff(original, updated) {
    const normalizedOriginal = normalizeUpdateObject(original);
    if (!_.isEqual(updated, normalizedOriginal)) {
        return {
            original: normalizedOriginal,
            updated: updated,
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
