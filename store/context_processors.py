from django.db.utils import OperationalError, ProgrammingError
from .models import Notification


def notifications(request):
    count = 0
    if request.user.is_authenticated:
        try:
            count = Notification.objects.filter(user=request.user, is_read=False).count()
        except (OperationalError, ProgrammingError):
            # Database not migrated yet or table missing
            count = 0
    return {
        'notification_unread_count': count
    }

from .models import CartItem, Category

def cart_count(request):
    """Add cart count to all templates"""
    if request.user.is_authenticated:
        count = CartItem.objects.filter(user=request.user).count()
        return {'cart_count': count}
    return {'cart_count': 0}

def categories(request):
    """Add categories to all templates"""
    return {'categories': Category.objects.all()} 