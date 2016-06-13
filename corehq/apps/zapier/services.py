from .models import Subscription


def delete_subscription_with_url(url):
    try:
        Subscription.objects.get(url=url).delete()
        return True
    except Subscription.DoesNotExist:
        return False
