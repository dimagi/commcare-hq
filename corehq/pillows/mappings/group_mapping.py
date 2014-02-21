GROUP_INDEX="hqgroups_1w49s2gcvfkv6ky0h7fp48ok54yhjlxb"
GROUP_MAPPING= {
    "date_formats": [
        "yyyy-MM-dd", 
        "yyyy-MM-dd'T'HH:mm:ssZZ", 
        "yyyy-MM-dd'T'HH:mm:ss.SSSSSS", 
        "yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'", 
        "yyyy-MM-dd'T'HH:mm:ss'Z'", 
        "yyyy-MM-dd'T'HH:mm:ssZ", 
        "yyyy-MM-dd'T'HH:mm:ssZZ'Z'", 
        "yyyy-MM-dd'T'HH:mm:ss.SSSZZ", 
        "yyyy-MM-dd'T'HH:mm:ss", 
        "yyyy-MM-dd' 'HH:mm:ss", 
        "yyyy-MM-dd' 'HH:mm:ss.SSSSSS", 
        "mm/dd/yy' 'HH:mm:ss"
    ], 
    "dynamic": False, 
    "_meta": {
        "comment": "Ethan created on 2014-02-11", 
        "created": None
    }, 
    "date_detection": False, 
    "properties": {
        "doc_type": {
            "index": "not_analyzed", 
            "type": "string"
        }, 
        "domain": {
            "fields": {
                "domain": {
                    "index": "analyzed", 
                    "type": "string"
                }, 
                "exact": {
                    "index": "not_analyzed", 
                    "type": "string"
                }
            }, 
            "type": "multi_field"
        }, 
        "name": {
            "fields": {
                "exact": {
                    "index": "not_analyzed", 
                    "type": "string"
                }, 
                "name": {
                    "index": "analyzed", 
                    "type": "string"
                }
            }, 
            "type": "multi_field"
        }, 
        "reporting": {"type": "boolean"}, 
        "path": {"type": "string"}, 
        "case_sharing": {"type": "boolean"}, 
        "users": {"type": "string"},
    }
}
