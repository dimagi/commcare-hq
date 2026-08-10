from corehq.form_processor.models import CommCareCase

def rows_to_cases(rows, table, domain, case_type):
    prop_columns = [col for col in table.columns if col.name.startswith('prop__')]
    return [
        CommCareCase(
            case_id=row['case_id'],
            domain=domain,
            type=case_type,
            name=row['case_name'],
            owner_id=row['owner_id'],
            opened_on=row['opened_on'],
            closed_on=row['closed_on'],
            closed=row['closed'],
            modified_on=row['modified_on'],
            server_modified_on=row['server_modified_on'],
            external_id=row['external_id'],
            # The column comment has the raw, untruncated property name
            case_json={col.comment: row[col.name] for col in prop_columns
                       if row[col.name]},
        ) for row in rows
    ]

def to_distance_in_meters(distance, unit):
    distance = float(distance)
    if unit == 'meters':
        return distance
    elif unit == 'kilometers':
        return distance * 1000
    elif unit == 'centimeters':
        return distance / 100
    elif unit == 'millimeters':
        return distance / 1000
    elif unit == 'miles':
        return distance * 1609.344
    elif unit == 'yards':
        return distance * 0.9144
    elif unit == 'feet':
        return distance * 0.3048
    elif unit == 'inch':
        return distance * 0.0254
    elif unit == 'nauticalmiles':
        return distance * 1852
    return None
