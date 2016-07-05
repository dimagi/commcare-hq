from .models import ZapierSubscription


def delete_subscription_with_url(url):
    try:
        ZapierSubscription.objects.get(url=url).delete()
        return True
    except ZapierSubscription.DoesNotExist:
        return False
