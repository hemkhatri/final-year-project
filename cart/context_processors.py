from .cart import Cart

def cart(request):
    """
    Returns the initialized Cart object globally to all templates.
    """
    return {'cart': Cart(request)}