from django.urls import path
from . import views
from .views import CustomLoginView  # Custom login view

urlpatterns = [
    path('', views.home, name='home'),
    path('product/<int:pk>/', views.product_detail, name='product_detail'),
    path('product/<int:pk>/edit/', views.edit_product, name='edit_product'),
    path('product/<int:pk>/delete/', views.delete_product, name='delete_product'),
    path('register/', views.register, name='register'),

    # ✅ Custom login view with success message
    path('login/', CustomLoginView.as_view(template_name='store/login.html'), name='login'),

    # ✅ Use custom logout view instead of LogoutView
    path('logout/', views.custom_logout, name='logout'),

    # Profile and dashboard
    path('profile/', views.profile, name='profile'),
    path('update-profile/', views.update_profile, name='update_profile'),
    
    # Cart functionality
    path('add-to-cart/<int:pk>/', views.add_to_cart, name='add_to_cart'),
    path('remove-from-cart/<int:pk>/', views.remove_from_cart, name='remove_from_cart'),
    path('update-cart-quantity/<int:pk>/', views.update_cart_quantity, name='update_cart_quantity'),
    path('cart/', views.cart, name='cart'),
    path('save-for-later/<int:pk>/', views.save_for_later, name='save_for_later'),
    
    # Wishlist functionality
    path('wishlist/', views.wishlist, name='wishlist'),
    path('remove-from-wishlist/<int:pk>/', views.remove_from_wishlist, name='remove_from_wishlist'),
    path('add-to-cart-from-wishlist/<int:pk>/', views.add_to_cart_from_wishlist, name='add_to_cart_from_wishlist'),
    
    # Cart sharing
    path('share-cart/', views.share_cart, name='share_cart'),
    path('shared-cart/<str:token>/', views.shared_cart, name='shared_cart'),
    
    # Checkout and orders
    path('checkout/', views.checkout, name='checkout'),
    path('checkout-success/', views.checkout_success, name='checkout_success'),
    # PayPal
    path('paypal/start/', views.paypal_start, name='paypal_start'),
    path('paypal/capture/', views.paypal_capture, name='paypal_capture'),
    path('coupons/', views.coupons_list, name='coupons_list'),
    path('apply-coupon/', views.apply_coupon, name='apply_coupon'),
    # Admin coupons management (not Django admin)
    path('manage/coupons/', views.coupons_manage, name='coupons_manage'),
    path('manage/coupons/new/', views.coupon_create, name='coupon_create'),
    path('manage/coupons/<int:pk>/delete/', views.coupon_delete, name='coupon_delete'),
    
    # Address management
    path('add-address/', views.add_address, name='add_address'),
    path('delete-address/<int:pk>/', views.delete_address, name='delete_address'),
    
    # Invoice download
    path('download-invoice/<int:order_id>/', views.download_invoice, name='download_invoice'),
    # Returns & Notifications
    path('return-request/<int:order_id>/', views.return_request_view, name='return_request'),
    path('notifications/', views.notifications_view, name='notifications'),
    path('notifications/<int:pk>/delete/', views.delete_notification, name='delete_notification'),
    path('returns/<int:pk>/approve/', views.approve_return, name='approve_return'),
    path('returns/<int:pk>/decline/', views.decline_return, name='decline_return'),
    # Chatbot
    path('api/chatbot/', views.chatbot_api, name='chatbot_api'),
    
    # Reviews
    path('add-review/<int:order_id>/', views.add_review, name='add_review'),

    # Admin tools (staff only)
    path('add-product/', views.add_product, name='add_product'),
    path('add-brand/', views.add_brand, name='add_brand'),
    path('manage-orders/', views.manage_orders, name='manage_orders'),
    path('add-category/', views.add_category, name='add_category'),
    
    # Policy Pages
    path('about-us/', views.about_us, name='about_us'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('terms-of-use/', views.terms_of_use, name='terms_of_use'),
    path('shipping-policy/', views.shipping_policy, name='shipping_policy'),
    path('return-policy/', views.return_policy, name='return_policy'),
    path('contact/', views.contact, name='contact'),
    

]
