from corehq.warehouse.const import (
    APP_STATUS_FACT_SLUG,
)


def app_status_transform(row):
    print row
    return row


def get_transform(slug):
    return TRANSFORMS.get(slug, lambda x: x)


TRANSFORMS = {
    APP_STATUS_FACT_SLUG: app_status_transform,
}
