# Exports

### Architecture

Exports are designed to build off the corresponding application to generate a schema that represents the questions, properties, and system properties that are available to the user to select. There is exactly one schema for each Application/Module/Form triplet or Application/Case Type pair. On initial generation of an export schema, each built application that has `has_submissions` set to True will be processed along with the current or "live" application.

Example:

Suppose there exists the following app builds

| app_id  | build_version | questions |
|---|---|---|
| 1234  | 12 (current) | q1,q2,q4   |
| 1234  | 10  | q1,q3   |
| 1234  | 1  | q1,q2,q3   |

Below illustrates what the schema will look like after processing each app from beginning to current. The example schema is simplified for understanding. Each question has an app_id and version associated with it.

After processing build_version 1:
```
q1.last_occurences = { app_id: 1 }
q2.last_occurences = { app_id: 1 }
q3.last_occurences = { app_id: 1 }
```

After processing build_version 10:
```
q1.last_occurences = { app_id: 10 }
q2.last_occurences = { app_id: 1 }
q3.last_occurences = { app_id: 10 }
```

After processing build_version 12 (current version, not necessarily built):
```
q1.last_occurences = { app_id: 12 }
q2.last_occurences = { app_id: 12 }
q3.last_occurences = { app_id: 10 }
q4.last_occurences = { app_id: 12 }
```

The export that is then generated will look something like this:

| question | is selected (by default) | is marked deleted | is hidden from user |
|------|---|---|---|
| q1 | ✓ |  |  |
| q2 | ✓ |  |  |
| q3 | | ✓ | ✓ |
| q4 | ✓ |  |  |

Since q3's latest build_version is 10, the code deduces that it has been deleted and therefore hides it and marks it as deleted.

### Optimizations

Often times iterating through each build in an application can be time consuming. To reduce the time to process an application, the code only processes applications that have been marked as having submissions.

### Caveats and edge cases

- Unknown deleted questions: It is possible to have an export where there lists properties that do not have any data associated with them. This case can arise when adding a question, `q1`, to the current application (without making a build), opening an export (to kick off the processing of the current application), then deleting `q1` before making a build. `q1` will now always be in the schema but will be shown as deleted.
- Case changes not immediately updated: When opening a case export, only the application that was chosen for the case type will be processed for the _current_ version. This means that if there exists another application that differs from the previous saved build and uses the same case type as another application, those updates will not show up until a build is made.
