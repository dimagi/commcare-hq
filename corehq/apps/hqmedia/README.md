# Multimedia

## General multimedia handling

Multimedia metadata is stored in couch, using `CommCareMultimedia` and its subclasses: `CommCareImage`, `CommCareAudio`, etc.

Each file is stored once, regardless of how many applications or domains use it. This is enforced via the [by_hash](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/hqmedia/_design/views/by_hash/map.js) view, which stores a hash of each multimedia file's content. When new multimedia is uploaded, the contents are hashed and looked up to determine wheether or not to create a new document. See `CommCareMultimedia.get_by_data` and its calling code in places like `BaseProcessFileUploadView.process_upload`.

These documents are never deleted.

## Multimedia in applications
