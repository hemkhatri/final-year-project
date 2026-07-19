from decimal import Decimal
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory
from django.urls import reverse

from cart.cart import Cart
from shop.models import Category, Product

User = get_user_model()


class CartUnitAndViewsTestCase(TestCase):
    def setUp(self):
        # 1. Guarantee fallback configurations for the session key
        if not hasattr(settings, 'CART_SESSION_ID'):
            settings.CART_SESSION_ID = 'cart'

        # 2. Setup mock target dependency users
        self.seller = User.objects.create_user(
            username='cart_seller', 
            password='testpassword123', 
            role=User.Role.SELLER
        )

        # 3. Build setup prerequisite catalog records
        self.category = Category.objects.create(name='Groceries', slug='groceries')
        self.product_1 = Product.objects.create(
            seller=self.seller,
            category=self.category,
            name='Organic Apples',
            slug='organic-apples',
            price=Decimal('250.00'),
            stock=50,
            available=True
        )
        self.product_2 = Product.objects.create(
            seller=self.seller,
            category=self.category,
            name='Fresh Milk',
            slug='fresh-milk',
            price=Decimal('120.00'),
            stock=30,
            available=True
        )

        # 4. Request Factory for testing class methods in isolation
        self.factory = RequestFactory()

    def get_cart_from_factory_session(self, initial_cart_data=None):
        """Helper to instantiate a Cart using a request factory containing session context."""
        request = self.factory.get('/')
        middleware = getattr(settings, 'MIDDLEWARE', [])
        
        # Simulating session container on vanilla request objects
        request.session = self.client.session
        if initial_cart_data is not None:
            request.session[settings.CART_SESSION_ID] = initial_cart_data
        else:
            request.session[settings.CART_SESSION_ID] = {}
        return Cart(request), request

    # ==========================================
    # PURE PYTHON CLASS UNIT TESTS (cart.py)
    # ==========================================

    def test_cart_initialization(self):
        """Ensure an empty session initiates a clean, empty cart tracking dictionary."""
        cart, _ = self.get_cart_from_factory_session()
        self.assertEqual(len(cart), 0)
        self.assertEqual(cart.get_total_price(), Decimal('0.00'))

    def test_cart_add_and_increment(self):
        """Adding items should increment values or append items correctly without overrides."""
        cart, _ = self.get_cart_from_factory_session()
        
        # Add 1st item
        cart.add(product=self.product_1, quantity=2)
        self.assertEqual(len(cart), 2)
        self.assertEqual(cart.get_total_price(), Decimal('500.00'))

        # Add same item again (increment check)
        cart.add(product=self.product_1, quantity=3)
        self.assertEqual(len(cart), 5)
        self.assertEqual(cart.get_total_price(), Decimal('1250.00'))

    def test_cart_add_with_override(self):
        """Adding an item with override_quantity=True resets the quantity parameter completely."""
        cart, _ = self.get_cart_from_factory_session()
        
        cart.add(product=self.product_1, quantity=5)
        # Override the quantity down to 2
        cart.add(product=self.product_1, quantity=2, override_quantity=True)
        
        self.assertEqual(len(cart), 2)
        self.assertEqual(cart.get_total_price(), Decimal('500.00'))

    def test_cart_remove(self):
        """Removing a product drops its internal dict tracking instance key completely."""
        cart, _ = self.get_cart_from_factory_session()
        
        cart.add(product=self.product_1, quantity=1)
        cart.add(product=self.product_2, quantity=2)
        self.assertEqual(len(cart), 3)

        # Drop first item
        cart.remove(self.product_1)
        self.assertEqual(len(cart), 2)
        self.assertEqual(cart.get_total_price(), Decimal('240.00')) # Only Milk remains

    def test_cart_iteration_and_decimal_casting(self):
        """Ensure looping through a cart evaluates mathematical structures and database relationships accurately."""
        initial_session_data = {
            str(self.product_1.id): {'quantity': 2, 'price': str(self.product_1.price)},
            str(self.product_2.id): {'quantity': 1, 'price': str(self.product_2.price)}
        }
        cart, _ = self.get_cart_from_factory_session(initial_cart_data=initial_session_data)

        items = list(cart)
        self.assertEqual(len(items), 2)

        # Inspect first yielding entry metadata
        item_1 = next(i for i in items if i['product'].id == self.product_1.id)
        self.assertIsInstance(item_1['price'], Decimal)
        self.assertIsInstance(item_1['total_price'], Decimal)
        self.assertEqual(item_1['total_price'], Decimal('500.00'))

    def test_cart_clear(self):
        """Clearing the cart drops the session identifier completely."""
        cart, request = self.get_cart_from_factory_session()
        cart.add(product=self.product_1, quantity=10)
        
        self.assertIn(settings.CART_SESSION_ID, request.session)
        cart.clear()
        self.assertNotIn(settings.CART_SESSION_ID, request.session)

    # ==========================================
    # VIEW INTERACTION FUNCTIONAL TESTS (views.py)
    # ==========================================

    def test_cart_detail_view_empty(self):
        """GET request to detail view renders empty cart interface components correctly."""
        response = self.client.get(reverse('cart:cart_detail'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'cart/cart_items.html')
        # Proves template block conditions map nicely
        self.assertContains(response, "Your shopping cart is currently empty.")

    def test_cart_detail_view_with_items(self):
        """GET request to detail view outputs active totals and pricing lists cleanly."""
        session = self.client.session
        session[settings.CART_SESSION_ID] = {
            str(self.product_1.id): {'quantity': 3, 'price': str(self.product_1.price)}
        }
        session.save()

        response = self.client.get(reverse('cart:cart_detail'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Organic Apples")
        self.assertContains(response, "Rs. 750.00") # Total amount verification inside HTML

    def test_cart_add_view(self):
        """POST request to cart_add view pushes tracking tokens straight to standard storage pools."""
        url = reverse('cart:cart_add', kwargs={'product_id': self.product_1.id})
        
        # Fire standard quick grid add button event handler click simulation
        response = self.client.post(url, data={'quantity': 3}, HTTP_REFERER='/market/')
        
        # Asserts view redirects back to client safe context fallback paths cleanly
        self.assertRedirects(response, '/market/', fetch_redirect_response=False)
        
        # Verify changes were saved directly to current cookie frameworks
        session_cart = self.client.session[settings.CART_SESSION_ID]
        self.assertIn(str(self.product_1.id), session_cart)
        self.assertEqual(session_cart[str(self.product_1.id)]['quantity'], 3)

    def test_cart_remove_view(self):
        """POST request to cart_remove targets active rows and purges entries smoothly."""
        session = self.client.session
        session[settings.CART_SESSION_ID] = {
            str(self.product_1.id): {'quantity': 5, 'price': str(self.product_1.price)},
            str(self.product_2.id): {'quantity': 1, 'price': str(self.product_2.price)}
        }
        session.save()

        url = reverse('cart:cart_remove', kwargs={'product_id': self.product_1.id})
        response = self.client.post(url)
        
        # Check standard navigation routing updates
        self.assertRedirects(response, reverse('cart:cart_detail'))
        
        # Check tracking parameters inside target collections
        updated_cart = self.client.session[settings.CART_SESSION_ID]
        self.assertNotIn(str(self.product_1.id), updated_cart)
        self.assertIn(str(self.product_2.id), updated_cart)