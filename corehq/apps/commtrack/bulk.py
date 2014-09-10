from corehq.apps.commtrack.models import *
from django.utils.translation import ugettext as _


def set_error(row, msg, override=False):
    """set an error message on a stock report to be imported"""
    if override or 'error' not in row:
        row['error'] = msg


def import_products(domain, importer):
    messages = []
    to_save = []
    product_count = 0

    for row in importer.worksheet:
        try:
            p = Product.from_excel(row)
            if p:
                if p.domain:
                    if p.domain != domain:
                        messages.append(
                            _(u"Product {product_name} belongs to another domain and was not updated").format(
                                product_name=p.name
                            )
                        )
                        continue
                else:
                    p.domain = domain

                product_count += 1
                to_save.append(p)

            importer.add_progress()

        except Exception, e:
            messages.append(
                _(u'Failed to import product {name}: {ex}'.format(
                    name=row['name'] or '',
                    ex=e,
                ))
            )

        if len(to_save) > 500:
            Product.get_db().bulk_save(to_save)
            to_save = []

    if to_save:
        Product.get_db().bulk_save(to_save)

    if product_count:
        messages.insert(0, _('Successfullly updated {number_of_products} products with {errors} errors.').format(
            number_of_products=product_count, errors=len(messages))
        )
    return messages
