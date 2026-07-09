from functools import wraps
from django.core.exceptions import PermissionDenied

def seller_required(view_func):
    @wraps(view_func)  # Keeps original view name and metadata intact
    def _wrapped_view_func(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role == "SELLER":
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped_view_func