# accounts/context_processors.py

def user_role_matrix(request):
    user = request.user
    
    # Default everything to False for anonymous guests
    roles = {
        'is_system_admin': False,
        'is_active_seller': False,
        'is_logistics_driver': False,
        'is_standard_customer': True,
    }
    
    if user.is_authenticated:
        roles['is_system_admin'] = getattr(user, 'is_staff', False)
        roles['is_active_seller'] = getattr(user, 'is_seller', False)
        roles['is_logistics_driver'] = getattr(user, 'is_delivery_boy', False)
        
        # A standard customer is logged in but holds no specialized staff/node roles
        if roles['is_system_admin'] or roles['is_active_seller'] or roles['is_logistics_driver']:
            roles['is_standard_customer'] = False
            
    return {'roles': roles}