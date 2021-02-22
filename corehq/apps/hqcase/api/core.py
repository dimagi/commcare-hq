def serialize_case(case):
    """Serializes a case for the V0.6 Case API"""
    return {
        "domain": case.domain,
        "@case_id": case.case_id,
        "@case_type": case.type,
        "case_name": case.name,
        "external_id": case.external_id,
        "@owner_id": case.owner_id,
        "date_opened": _isoformat(case.opened_on),
        "last_modified": _isoformat(case.modified_on),
        "server_last_modified": _isoformat(case.server_modified_on),
        "closed": case.closed,
        "date_closed": _isoformat(case.closed_on),
        "properties": dict(case.dynamic_case_properties()),
        "indices": {
            index.identifier: {
                "case_id": index.referenced_id,
                "@case_type": index.referenced_type,
                "@relationship": index.relationship,
            }
            for index in case.indices
        }
    }


def _isoformat(value):
    return value.isoformat() if value else None


class UserError(Exception):
    pass


class SubmissionError(Exception):
    def __init__(self, msg, form_id):
        self.form_id = form_id
        super().__init__(msg)


