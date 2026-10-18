from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.contrib.auth import logout
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
import json
import re
import random
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Avg, Count
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

import json
from datetime import timedelta
import uuid
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from decimal import Decimal
import os
from django.conf import settings
from io import BytesIO
import requests

from .models import (
    Chocolate, CartItem, Order, Category, WishlistItem, UserAddress, CartShare,
    UserProfile, Review, BirthdayOffer, ReturnRequest, Notification, Brand
)
from stock_and_location.models import StoreLocation
from delivery.models import DeliveryAgent, DeliveryAssignment


# --- ETA helper -------------------------------------------------------------
def estimate_eta(address, store):
    """
    Return a tuple (days_for_expected_date, human_window_text)
    using simple tiers (no geocoding):
      - Same city → 2–6 hours (0 days)
      - Same state → 1–2 days (1 day)
      - Different state/country/unknown → 3–5 days (3 days)
    """
    try:
        if not address or not store:
            return 3, "3–5 days"
        city_a = (address.city or '').strip().lower()
        state_a = (address.state or '').strip().lower()
        city_s = (store.city or '').strip().lower()
        state_s = (store.state or '').strip().lower()

        if city_a and city_s and city_a == city_s:
            return 0, "2–6 hours"
        if state_a and state_s and state_a == state_s:
            return 1, "1–2 days"
        return 3, "3–5 days"
    except Exception:
        return 3, "3–5 days"


def home(request):
    category_id = request.GET.get('category')
    brand_id = request.GET.get('brand')
    sort_by = request.GET.get('sort', 'name')
    sort_order = request.GET.get('order', 'asc')
    
    # Get chocolates with filtering and sorting
    chocolates = Chocolate.objects.all()
    
    if category_id:
        chocolates = chocolates.filter(category_id=category_id)
    if brand_id:
        chocolates = chocolates.filter(brand_id=brand_id)
    
    # Apply sorting
    if sort_by == 'name':
        chocolates = chocolates.order_by('name' if sort_order == 'asc' else '-name')
    elif sort_by == 'price':
        chocolates = chocolates.order_by('price' if sort_order == 'asc' else '-price')
    elif sort_by == 'sales':
        chocolates = chocolates.order_by('-total_sales')
    elif sort_by == 'rating':
        chocolates = chocolates.order_by('-rating')
    else:
        chocolates = chocolates.order_by('name')
    
    categories = Category.objects.all()
    brands_all = Brand.objects.all()
    brands_top = Brand.objects.filter(is_top=True)

    # Determine the single most purchased product across all users
    most_purchased = (
        Order.objects.values('chocolate')
        .annotate(user_count=Count('user', distinct=True))
        .order_by('-user_count')
        .first()
    )
    most_purchased_id = most_purchased['chocolate'] if most_purchased and most_purchased.get('user_count', 0) > 0 else None
    
    # Get cart count for authenticated users
    cart_count = 0
    birthday_offer = None
    if request.user.is_authenticated:
        cart_count = CartItem.objects.filter(user=request.user).count()
        
        # Check for birthday offers
        try:
            profile = UserProfile.objects.get(user=request.user)
            if profile.is_birthday_today():
                birthday_offer, created = BirthdayOffer.objects.get_or_create(
                    user=request.user,
                    is_used=False,
                    defaults={'expires_at': timezone.now() + timedelta(days=1)}
                )
        except UserProfile.DoesNotExist:
            pass
    
    return render(request, 'store/home.html', {
        'chocolates': chocolates,
        'categories': categories,
        'brands_all': brands_all,
        'brands_top': brands_top,
        'cart_count': cart_count,
        'birthday_offer': birthday_offer,
        'current_sort': sort_by,
        'current_order': sort_order,
        'most_purchased_id': most_purchased_id,
    })


@login_required
def paypal_start(request):
    """
    Create a PayPal order and redirect the user to PayPal approval.
    """
    if request.method != 'POST':
        return redirect('checkout')

    # Persist the selected address in session
    address_id = request.POST.get('address')
    address = None
    if address_id:
        address = get_object_or_404(UserAddress, id=address_id, user=request.user)
        request.session['selected_address_id'] = address.id
    else:
        request.session.pop('selected_address_id', None)

    # Compute totals similar to checkout
    cart_items = CartItem.objects.filter(user=request.user)
    if not cart_items.exists():
        messages.error(request, 'Your cart is empty.')
        return redirect('cart')

    total = sum(item.total_price() for item in cart_items)
    applied_coupon_code = request.session.get('applied_coupon_code')
    try:
        subtotal = Decimal(str(total))
        if applied_coupon_code:
            from .models import Coupon
            applied_coupon = Coupon.objects.get(code__iexact=applied_coupon_code)
            discount = applied_coupon.calculate_discount(subtotal)
        else:
            discount = Decimal('0.00')
        taxable = (subtotal - discount)
        if taxable < Decimal('0.00'):
            taxable = Decimal('0.00')
        tax_amount = (taxable * Decimal('0.05')).quantize(Decimal('0.01'))
        delivery_fee = Decimal('20.00')
        if applied_coupon_code and applied_coupon_code.upper() == 'FREESHIP' and subtotal >= Decimal('1000'):
            delivery_fee = Decimal('0.00')
        grand_total = (taxable + tax_amount + delivery_fee).quantize(Decimal('0.01'))
    except Exception:
        messages.error(request, 'Unable to compute totals for payment.')
        return redirect('checkout')

    # Save amount in session for verification after capture
    request.session['pending_payment_amount'] = str(grand_total)

    # PayPal OAuth token
    base = 'https://api-m.sandbox.paypal.com' if settings.PAYPAL_ENV == 'sandbox' else 'https://api-m.paypal.com'
    try:
        auth_resp = requests.post(
            f"{base}/v1/oauth2/token",
            data={'grant_type': 'client_credentials'},
            auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_CLIENT_SECRET),
            timeout=20,
        )
        if auth_resp.status_code != 200:
            try:
                err = auth_resp.json()
                desc = err.get('error_description') or err.get('message') or auth_resp.text
            except Exception:
                desc = auth_resp.text
            messages.error(request, f"PayPal auth failed: {desc}")
            return redirect('checkout')
        access_token = auth_resp.json().get('access_token')
    except requests.RequestException as e:
        messages.error(request, f"Failed to contact PayPal: {str(e)}")
        return redirect('checkout')

    # Build return/cancel URLs
    return_url = settings.PUBLIC_BASE_URL.rstrip('/') + reverse('paypal_capture')
    cancel_url = settings.PUBLIC_BASE_URL.rstrip('/') + reverse('checkout')

    # Create Order
    # Use USD in Sandbox to avoid currency validation issues
    currency = 'USD'
    order_body = {
        'intent': 'CAPTURE',
        'purchase_units': [
            {
                'amount': {
                    'currency_code': currency,
                    'value': f"{grand_total:.2f}",
                }
            }
        ],
        'application_context': {
            'brand_name': 'GourmetGrove',
            'landing_page': 'NO_PREFERENCE',
            'user_action': 'PAY_NOW',
            'return_url': return_url,
            'cancel_url': cancel_url,
        }
    }

    try:
        create_resp = requests.post(
            f"{base}/v2/checkout/orders",
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {access_token}'},
            json=order_body,
            timeout=20,
        )
        if create_resp.status_code not in (200, 201):
            try:
                err = create_resp.json()
                details = err.get('details') or []
                detail_txt = '; '.join([d.get('issue', '') + (f" - {d.get('description')}" if d.get('description') else '') for d in details])
                base_msg = err.get('message') or create_resp.text
                msg = f"{base_msg}{(' | ' + detail_txt) if detail_txt else ''}"
            except Exception:
                msg = create_resp.text
            messages.error(request, f"PayPal order creation failed: {msg}")
            return redirect('checkout')
        data = create_resp.json()
        approval = next((l['href'] for l in data.get('links', []) if l.get('rel') == 'approve'), None)
        if not approval:
            messages.error(request, 'Failed to find PayPal approval link.')
            return redirect('checkout')
        # Keep PayPal order id in session for reference
        request.session['paypal_order_id'] = data.get('id')
        return redirect(approval)
    except requests.RequestException as e:
        messages.error(request, f"Failed to initiate PayPal payment: {str(e)}")
        return redirect('checkout')


@login_required
def paypal_capture(request):
    """
    Capture PayPal order after user approval, then create local orders and clear cart.
    """
    token = request.GET.get('token')  # PayPal order ID
    if not token:
        messages.error(request, 'Payment was canceled or failed.')
        return redirect('checkout')

    base = 'https://api-m.sandbox.paypal.com' if settings.PAYPAL_ENV == 'sandbox' else 'https://api-m.paypal.com'
    try:
        auth_resp = requests.post(
            f"{base}/v1/oauth2/token",
            data={'grant_type': 'client_credentials'},
            auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_CLIENT_SECRET),
            timeout=20,
        )
        if auth_resp.status_code != 200:
            try:
                err = auth_resp.json()
                desc = err.get('error_description') or err.get('message') or auth_resp.text
            except Exception:
                desc = auth_resp.text
            messages.error(request, f"PayPal auth failed: {desc}")
            return redirect('checkout')
        access_token = auth_resp.json().get('access_token')
    except requests.RequestException as e:
        messages.error(request, f"Failed to contact PayPal: {str(e)}")
        return redirect('checkout')

    try:
        cap_resp = requests.post(
            f"{base}/v2/checkout/orders/{token}/capture",
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {access_token}'},
            timeout=20,
        )
        if cap_resp.status_code not in (200, 201):
            try:
                err = cap_resp.json()
                msg = err.get('message') or cap_resp.text
            except Exception:
                msg = cap_resp.text
            messages.error(request, f"PayPal capture failed: {msg}")
            return redirect('checkout')
        cap = cap_resp.json()
    except requests.RequestException as e:
        messages.error(request, f"Failed to capture PayPal payment: {str(e)}")
        return redirect('checkout')

    # Basic verification of amount (optional: compare to session amount)
    expected = Decimal(request.session.get('pending_payment_amount', '0') or '0')
    try:
        pu = cap.get('purchase_units', [{}])[0]
        payments = pu.get('payments', {})
        captures = payments.get('captures', [])
        paid_value = Decimal(captures[0]['amount']['value']) if captures else expected
    except Exception:
        paid_value = expected

    # Create local orders only if amounts look OK
    if expected and paid_value and paid_value >= expected:
        cart_items = CartItem.objects.filter(user=request.user)
        if not cart_items.exists():
            # Nothing to create; just proceed
            messages.info(request, 'Payment captured.')
            return redirect('checkout_success')

        address = None
        addr_id = request.session.get('selected_address_id')
        if addr_id:
            try:
                address = UserAddress.objects.get(id=addr_id, user=request.user)
            except UserAddress.DoesNotExist:
                address = None

        created_orders = []
        for item in cart_items:
            created_orders.append(Order.objects.create(
                user=request.user,
                chocolate=item.chocolate,
                quantity=item.quantity,
                address=address
            ))

        # For each created order, assign nearest store + available delivery agent
        def nearest_store_for_address(addr):
            try:
                stores = StoreLocation.objects.filter(is_active=True)
                if addr and addr.city:
                    same_city = stores.filter(city__iexact=addr.city).first()
                    if same_city:
                        return same_city
                return stores.first()
            except Exception:
                return None

        for o in created_orders:
            store = nearest_store_for_address(address)
            agent = None
            if store:
                # Prefer available at same store
                agent = DeliveryAgent.objects.filter(is_active=True, is_available=True, store_location=store).first()
                # Fallback: any active at same store
                if not agent:
                    agent = DeliveryAgent.objects.filter(is_active=True, store_location=store).first()
            # Fallback: any available anywhere
            if not agent:
                agent = DeliveryAgent.objects.filter(is_active=True, is_available=True).first()
            # Last resort: any agent
            if not agent:
                agent = DeliveryAgent.objects.first()
            # Create assignment (even if agent is None)
            try:
                eta_days, _eta_window = estimate_eta(address, store)
                DeliveryAssignment.objects.create(
                    order=o,
                    agent=agent,
                    expected_delivery_date=(timezone.now() + timedelta(days=eta_days)).date(),
                )
            except Exception:
                # Fail silently; success page will fallback
                pass

        # Apply coupon usage to first order, if any
        applied_coupon_code = request.session.get('applied_coupon_code')
        if applied_coupon_code and created_orders:
            from .models import Coupon, CouponUsage
            try:
                c = Coupon.objects.get(code__iexact=applied_coupon_code)
                discount_amount = c.calculate_discount(Decimal(str(sum(i.total_price() for i in cart_items))))
                c.use_coupon(request.user, created_orders[0])
                cu = CouponUsage.objects.get(coupon=c, user=request.user, order=created_orders[0])
                cu.discount_amount = discount_amount
                cu.save(update_fields=['discount_amount'])
            except Exception:
                pass
            request.session.pop('applied_coupon_code', None)

        # Clear cart
        cart_items.delete()

        # Put recent order ids into session for success page
        try:
            request.session['recent_order_ids'] = [o.id for o in created_orders]
        except Exception:
            pass

        # Create a Notification for the user summarizing the success box
        try:
            primary_order = created_orders[0] if created_orders else None
            if primary_order:
                assign = DeliveryAssignment.objects.filter(order=primary_order).first()
                agent = assign.agent if assign else None
                store = agent.store_location if agent and agent.store_location else None
                eta_text = assign.expected_delivery_date.strftime('%d %b %Y') if (assign and assign.expected_delivery_date) else None
                _days, eta_window = estimate_eta(primary_order.address, store)

                parts = [
                    f"Order placed: ORD-{primary_order.id}",
                ]
                if primary_order.invoice_number:
                    parts.append(f"Invoice: {primary_order.invoice_number}")
                if agent:
                    phone = agent.phone_number or 'N/A'
                    parts.append(f"Agent: {agent.name} ({phone})")
                if store:
                    city = f", {store.city}" if getattr(store, 'city', None) else ''
                    parts.append(f"Store: {store.name}{city}")
                if eta_window or eta_text:
                    eta_piece = eta_window or ''
                    if eta_text:
                        eta_piece = (eta_piece + f" (by {eta_text})").strip()
                    parts.append(f"ETA: {eta_piece}")

                Notification.objects.create(
                    user=request.user,
                    message=' • '.join(parts)
                )
        except Exception:
            pass

    # Compute ETA window text from address + store for display
    if primary_order:
        try:
            _days, eta_window = estimate_eta(primary_order.address, store)
        except Exception:
            eta_window = None

        # Cleanup session keys
        for k in ['pending_payment_amount', 'selected_address_id', 'paypal_order_id']:
            request.session.pop(k, None)

        messages.success(request, 'Payment successful and order placed!')
        return redirect('checkout_success')
    else:
        messages.warning(request, 'Payment amount mismatch. Please contact support with your receipt.')
        return redirect('checkout')


def product_detail(request, pk):
    chocolate = get_object_or_404(Chocolate, pk=pk)
    categories = Category.objects.all()
    
    # Get cart count for authenticated users
    cart_count = 0
    user_review = None
    if request.user.is_authenticated:
        cart_count = CartItem.objects.filter(user=request.user).count()
        
        # Check if user has purchased this product
        user_orders = Order.objects.filter(user=request.user, chocolate=chocolate)
        if user_orders.exists():
            # Get user's review if exists
            user_review = Review.objects.filter(user=request.user, chocolate=chocolate).first()
    
    # Get all reviews for this product
    reviews = Review.objects.filter(chocolate=chocolate).order_by('-created_at')
    
    return render(request, 'store/product_detail.html', {
        'chocolate': chocolate,
        'categories': categories,
        'cart_count': cart_count,
        'reviews': reviews,
        'user_review': user_review,
        'user_orders': user_orders if request.user.is_authenticated else None,
    })


@staff_member_required
def add_product(request):
    categories = Category.objects.all()
    brands = Brand.objects.all()
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        price = request.POST.get('price')
        category_id = request.POST.get('category')
        brand_id = request.POST.get('brand')
        image = request.FILES.get('image')

        if not (name and description and price and category_id):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'store/add_product.html', {
                'categories': categories,
                'brands': brands,
                'form_data': request.POST,
            })

        try:
            category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            messages.error(request, 'Selected category does not exist.')
            return render(request, 'store/add_product.html', {
                'categories': categories,
                'form_data': request.POST,
            })

        chocolate = Chocolate(
            name=name,
            description=description,
            price=price,
            category=category,
        )
        # Optional brand
        if brand_id:
            try:
                chocolate.brand = Brand.objects.get(id=brand_id)
            except Brand.DoesNotExist:
                pass
        if image:
            chocolate.image = image
        chocolate.save()
        messages.success(request, f'Product "{chocolate.name}" added successfully!')
        return redirect('product_detail', pk=chocolate.pk)

    return render(request, 'store/add_product.html', {
        'categories': categories,
        'brands': brands,
    })


@staff_member_required
def add_brand(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        is_top = request.POST.get('is_top') == 'on'
        image = request.FILES.get('image')

        if not name:
            messages.error(request, 'Please provide a brand name.')
            return render(request, 'store/add_brand.html', {
                'form_data': request.POST,
            })

        # Prevent duplicate names
        if Brand.objects.filter(name__iexact=name).exists():
            messages.error(request, 'A brand with this name already exists.')
            return render(request, 'store/add_brand.html', {
                'form_data': request.POST,
            })

        brand = Brand(name=name, is_top=is_top)
        if image:
            brand.image = image
        brand.save()
        messages.success(request, f'Brand "{brand.name}" added successfully!')
        return redirect('home')

    return render(request, 'store/add_brand.html')

@staff_member_required
def manage_orders(request):
    orders = Order.objects.select_related('user', 'chocolate').order_by('-created_at')
    return render(request, 'store/manage_orders.html', {
        'orders': orders,
    })

@staff_member_required
def edit_product(request, pk):
    chocolate = get_object_or_404(Chocolate, pk=pk)
    categories = Category.objects.all()
    
    if request.method == 'POST':
        # Handle form submission for editing
        chocolate.name = request.POST.get('name', chocolate.name)
        chocolate.description = request.POST.get('description', chocolate.description)
        chocolate.price = request.POST.get('price', chocolate.price)
        category_id = request.POST.get('category')
        if category_id:
            chocolate.category = Category.objects.get(id=category_id)
        
        # Handle image upload if provided
        if 'image' in request.FILES:
            chocolate.image = request.FILES['image']
        
        chocolate.save()
        messages.success(request, f"{chocolate.name} updated successfully!")
        return redirect('product_detail', pk=chocolate.pk)
    
    return render(request, 'store/edit_product.html', {
        'chocolate': chocolate,
        'categories': categories,
    })


@staff_member_required
def delete_product(request, pk):
    chocolate = get_object_or_404(Chocolate, pk=pk)
    
    if request.method == 'POST':
        chocolate_name = chocolate.name
        chocolate.delete()
        messages.success(request, f"{chocolate_name} deleted successfully!")
        return redirect('home')
    
    return render(request, 'store/delete_confirm.html', {
        'chocolate': chocolate,
        'categories': Category.objects.all(),
    })


@staff_member_required
def add_category(request):
    categories = Category.objects.all()
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        if not name:
            messages.error(request, 'Please enter a category name.')
            return render(request, 'store/add_category.html', {
                'categories': categories,
                'form_data': request.POST,
            })
        from .models import Category as Cat
        if Cat.objects.filter(name__iexact=name).exists():
            messages.error(request, 'A category with this name already exists.')
            return render(request, 'store/add_category.html', {
                'categories': categories,
                'form_data': request.POST,
            })
        Cat.objects.create(name=name)
        messages.success(request, f'Category "{name}" added successfully!')
        return redirect('home')
    return render(request, 'store/add_category.html', {
        'categories': categories,
    })

@login_required
def return_request_view(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if order.user != request.user:
        messages.error(request, 'You can only request a return for your own orders.')
        return redirect('profile')

    if request.method == 'POST':
        reason = request.POST.get('reason')
        reason_other = request.POST.get('reason_other', '').strip()
        if not reason:
            messages.error(request, 'Please select a reason for return.')
        else:
            rr = ReturnRequest.objects.create(
                user=request.user,
                order=order,
                reason=reason,
                reason_other=reason_other if reason == 'other' else ''
            )
            # Notify all staff users
            from django.contrib.auth.models import User as AuthUser
            for admin_user in AuthUser.objects.filter(is_staff=True):
                Notification.objects.create(
                    user=admin_user,
                    message=f"New return request #{rr.id} for order {order.invoice_number} by {request.user.username}",
                    return_request=rr
                )
            messages.success(request, 'Your return request has been submitted.')
            return redirect('notifications')

    categories = Category.objects.all()
    return render(request, 'store/return_request.html', {
        'order': order,
        'categories': categories,
    })


@login_required
def notifications_view(request):
    notes = Notification.objects.filter(user=request.user).select_related('return_request').order_by('-created_at')
    # Mark all as read when visiting
    notes.filter(is_read=False).update(is_read=True)
    categories = Category.objects.all()
    # For admins, also include pending return requests for convenience
    pending_returns = []
    if request.user.is_staff:
        pending_returns = ReturnRequest.objects.select_related('order', 'user').filter(status=ReturnRequest.Status.PENDING).order_by('-created_at')
    return render(request, 'store/notifications.html', {
        'notifications': notes,
        'pending_returns': pending_returns,
        'categories': categories,
    })

 
@staff_member_required
def approve_return(request, pk):
    rr = get_object_or_404(ReturnRequest, pk=pk)
    if rr.status != ReturnRequest.Status.PENDING:
        messages.info(request, 'This return request has already been processed.')
        return redirect('notifications')
    rr.status = ReturnRequest.Status.APPROVED
    rr.decided_by = request.user
    rr.save()
    # Notify requester
    Notification.objects.create(
        user=rr.user,
        message=f"Your return request #{rr.id} for order {rr.order.invoice_number} was approved.",
        return_request=rr
    )
    messages.success(request, 'Return request approved.')
    return redirect('notifications')


@staff_member_required
def decline_return(request, pk):
    rr = get_object_or_404(ReturnRequest, pk=pk)
    if rr.status != ReturnRequest.Status.PENDING:
        messages.info(request, 'This return request has already been processed.')
        return redirect('notifications')
    rr.status = ReturnRequest.Status.DECLINED
    rr.decided_by = request.user
    rr.save()
    # Notify requester
    Notification.objects.create(
        user=rr.user,
        message=f"Your return request #{rr.id} for order {rr.order.invoice_number} was declined.",
        return_request=rr
    )
    messages.success(request, 'Return request declined.')
    return redirect('notifications')


@login_required
def delete_notification(request, pk):
    note = get_object_or_404(Notification, pk=pk, user=request.user)
    note.delete()
    messages.success(request, 'Notification deleted.')
    return redirect('notifications')


# --- Admin Coupon Management ---
@staff_member_required
def coupons_manage(request):
    from .models import Coupon
    coupons = Coupon.objects.all().order_by('-created_at')
    categories = Category.objects.all()
    cart_count = CartItem.objects.filter(user=request.user).count() if request.user.is_authenticated else 0
    return render(request, 'store/coupons_manage.html', {
        'coupons': coupons,
        'categories': categories,
        'cart_count': cart_count,
    })


@staff_member_required
def coupon_create(request):
    from .models import Coupon
    if request.method == 'POST':
        from decimal import Decimal
        from django.utils import timezone
        code = (request.POST.get('code') or '').strip()
        if not code:
            messages.error(request, 'Code is required')
        else:
            try:
                coupon = Coupon.objects.create(
                    code=code,
                    description=(request.POST.get('description') or '').strip(),
                    discount_type=request.POST.get('discount_type') or 'percentage',
                    discount_value=Decimal(request.POST.get('discount_value') or '0'),
                    minimum_order_amount=Decimal(request.POST.get('minimum_order_amount') or '0'),
                    maximum_discount_amount=(Decimal(request.POST.get('maximum_discount_amount')) if request.POST.get('maximum_discount_amount') else None),
                    usage_limit=(int(request.POST.get('usage_limit')) if request.POST.get('usage_limit') else None),
                    is_active=bool(request.POST.get('is_active')),
                    valid_from=timezone.now(),
                    valid_until=timezone.now() + timedelta(days=365),
                    created_by=request.user,
                )
                messages.success(request, f"Coupon {coupon.code} created")
                return redirect('coupons_manage')
            except Exception as e:
                messages.error(request, f"Failed to create coupon: {e}")
    categories = Category.objects.all()
    cart_count = CartItem.objects.filter(user=request.user).count() if request.user.is_authenticated else 0
    return render(request, 'store/coupon_form.html', {
        'categories': categories,
        'cart_count': cart_count,
    })


@staff_member_required
def coupon_delete(request, pk):
    from .models import Coupon
    if request.method == 'POST':
        try:
            c = Coupon.objects.get(pk=pk)
            code = c.code
            c.delete()
            messages.success(request, f"Coupon {code} deleted")
        except Coupon.DoesNotExist:
            messages.error(request, 'Coupon not found')
    return redirect('coupons_manage')


def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Create user profile
            UserProfile.objects.create(user=user)
            messages.success(request, 'Account created successfully! Please login.')
            return redirect('login')
    else:
        form = UserCreationForm()
    categories = Category.objects.all()
    return render(request, 'store/register.html', {'form': form, 'categories': categories})


@login_required
def profile(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    addresses = UserAddress.objects.filter(user=request.user).order_by('-is_default', '-created_at')
    categories = Category.objects.all()
    
    # Get or create user profile
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Get cart count
    cart_count = CartItem.objects.filter(user=request.user).count()
    
    # Check for birthday offer
    birthday_offer = None
    if profile.is_birthday_today():
        birthday_offer, created = BirthdayOffer.objects.get_or_create(
            user=request.user,
            is_used=False,
            defaults={'expires_at': timezone.now() + timedelta(days=1)}
        )
    
    return render(request, 'store/profile.html', {
        'orders': orders, 
        'addresses': addresses,
        'categories': categories,
        'cart_count': cart_count,
        'profile': profile,
        'birthday_offer': birthday_offer,
    })


@login_required
def update_profile(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # Update profile information
        if 'profile_picture' in request.FILES:
            profile.profile_picture = request.FILES['profile_picture']
        
        profile.phone_number = request.POST.get('phone_number', profile.phone_number)
        
        birth_date = request.POST.get('birth_date')
        if birth_date:
            profile.birth_date = birth_date
        
        # Update email if provided
        email = request.POST.get('email')
        if email and email != request.user.email:
            # Check if email is already taken by another user
            from django.contrib.auth.models import User
            if User.objects.filter(email=email).exclude(id=request.user.id).exists():
                messages.error(request, 'This email is already registered by another user.')
                return redirect('update_profile')
            else:
                request.user.email = email
                request.user.save()
        
        profile.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')
    
    categories = Category.objects.all()
    cart_count = CartItem.objects.filter(user=request.user).count()
    
    return render(request, 'store/update_profile.html', {
        'profile': profile,
        'categories': categories,
        'cart_count': cart_count,
    })


def add_to_cart(request, pk):
    if not request.user.is_authenticated:
        messages.warning(request, 'Please login to add items to cart.')
        return redirect('login')
    
    chocolate = get_object_or_404(Chocolate, pk=pk)
    item, created = CartItem.objects.get_or_create(user=request.user, chocolate=chocolate)
    if not created:
        item.quantity += 1
        item.save()
    messages.success(request, f"{chocolate.name} added to cart!")
    # Do not open cart automatically; return to previous page or home
    next_url = request.META.get('HTTP_REFERER') or request.GET.get('next') or request.POST.get('next') or reverse('home')
    return redirect(next_url)


@login_required
def remove_from_cart(request, pk):
    cart_item = get_object_or_404(CartItem, pk=pk, user=request.user)
    chocolate_name = cart_item.chocolate.name
    cart_item.delete()
    messages.success(request, f"{chocolate_name} removed from cart!")
    return redirect('cart')


@login_required
def update_cart_quantity(request, pk):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            action = data.get('action')
            cart_item = get_object_or_404(CartItem, pk=pk, user=request.user)
            
            if action == 'increase':
                cart_item.quantity += 1
            elif action == 'decrease':
                if cart_item.quantity > 1:
                    cart_item.quantity -= 1
                else:
                    cart_item.delete()
                    return JsonResponse({'status': 'removed'})
            
            cart_item.save()
            return JsonResponse({
                'status': 'success',
                'quantity': cart_item.quantity,
                'total_price': float(cart_item.total_price()),
                'cart_total': float(sum(item.total_price() for item in CartItem.objects.filter(user=request.user)))
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


@login_required
def cart(request):
    cart_items = CartItem.objects.filter(user=request.user)
    total = sum(item.total_price() for item in cart_items)
    cart_count = cart_items.count()
    categories = Category.objects.all()
    
    # Clear cart after inactivity (30 minutes)
    inactive_threshold = timezone.now() - timedelta(minutes=30)
    inactive_items = cart_items.filter(last_updated__lt=inactive_threshold)
    if inactive_items.exists():
        inactive_items.delete()
        messages.info(request, "Cart cleared due to inactivity.")
        return redirect('cart')
    
    return render(request, 'store/cart.html', {
        'cart_items': cart_items, 
        'total': total,
        'cart_count': cart_count,
        'categories': categories
    })


@login_required
def save_for_later(request, pk):
    cart_item = get_object_or_404(CartItem, pk=pk, user=request.user)
    chocolate = cart_item.chocolate
    
    # Add to wishlist
    WishlistItem.objects.get_or_create(user=request.user, chocolate=chocolate)
    
    # Remove from cart
    cart_item.delete()
    
    messages.success(request, f"{chocolate.name} moved to wishlist!")
    return redirect('cart')


@login_required
def wishlist(request):
    wishlist_items = WishlistItem.objects.filter(user=request.user).order_by('-added_at')
    categories = Category.objects.all()
    cart_count = CartItem.objects.filter(user=request.user).count()
    
    return render(request, 'store/wishlist.html', {
        'wishlist_items': wishlist_items,
        'categories': categories,
        'cart_count': cart_count,
    })


@login_required
def remove_from_wishlist(request, pk):
    wishlist_item = get_object_or_404(WishlistItem, pk=pk, user=request.user)
    chocolate_name = wishlist_item.chocolate.name
    wishlist_item.delete()
    messages.success(request, f"{chocolate_name} removed from wishlist!")
    return redirect('wishlist')


@login_required
def add_to_cart_from_wishlist(request, pk):
    wishlist_item = get_object_or_404(WishlistItem, pk=pk, user=request.user)
    chocolate = wishlist_item.chocolate
    
    # Add to cart
    cart_item, created = CartItem.objects.get_or_create(user=request.user, chocolate=chocolate)
    if not created:
        cart_item.quantity += 1
        cart_item.save()
    
    # Remove from wishlist
    wishlist_item.delete()
    
    messages.success(request, f"{chocolate.name} moved to cart!")
    return redirect('wishlist')


@login_required
def share_cart(request):
    # Create or get existing cart share
    cart_share, created = CartShare.objects.get_or_create(
        user=request.user,
        is_active=True,
        defaults={'expires_at': timezone.now() + timedelta(hours=24)}
    )
    
    if not created:
        cart_share.expires_at = timezone.now() + timedelta(hours=24)
        cart_share.save()
    
    share_url = request.build_absolute_uri(f'/shared-cart/{cart_share.share_token}/')
    return JsonResponse({'share_url': share_url})


def shared_cart(request, token):
    try:
        cart_share = CartShare.objects.get(share_token=token, is_active=True)
        if cart_share.is_expired():
            messages.error(request, 'This shared cart link has expired.')
            return redirect('home')
        
        cart_items = CartItem.objects.filter(user=cart_share.user)
        total = sum(item.total_price() for item in cart_items)
        categories = Category.objects.all()
        
        return render(request, 'store/shared_cart.html', {
            'cart_items': cart_items,
            'total': total,
            'shared_by': cart_share.user.username,
            'categories': categories,
        })
    except CartShare.DoesNotExist:
        messages.error(request, 'Invalid shared cart link.')
        return redirect('home')


@login_required
def checkout(request):
    cart_items = CartItem.objects.filter(user=request.user)
    total = sum(item.total_price() for item in cart_items)
    # Coupon handling
    applied_coupon_code = request.session.get('applied_coupon_code')
    applied_discount = None
    applied_coupon = None
    # Allow applying coupon via POST without placing order
    if request.method == "POST" and request.POST.get('action') == 'apply_coupon':
        code = (request.POST.get('coupon_code') or '').strip()
        if code:
            from .models import Coupon
            from django.utils import timezone
            try:
                c = Coupon.objects.get(code__iexact=code)
                from decimal import Decimal
                subtotal_tmp = Decimal(str(total))
                ok, msg = c.can_be_used_by_user(request.user, subtotal_tmp)
                if ok:
                    discount_amt = c.calculate_discount(subtotal_tmp)
                    request.session['applied_coupon_code'] = c.code
                    messages.success(request, f"Coupon '{c.code}' applied: Rs. {discount_amt}")
                    applied_coupon_code = c.code
                else:
                    request.session.pop('applied_coupon_code', None)
                    messages.error(request, msg)
                    applied_coupon_code = None
            except Coupon.DoesNotExist:
                request.session.pop('applied_coupon_code', None)
                messages.error(request, 'Invalid coupon code')
        else:
            request.session.pop('applied_coupon_code', None)
            messages.info(request, 'Coupon removed')

    # Calculate 5% tax and grand total for order summary, considering coupon discount and delivery
    try:
        from decimal import Decimal
        subtotal = Decimal(str(total))
        # Discount
        if applied_coupon_code:
            from .models import Coupon
            applied_coupon = Coupon.objects.get(code__iexact=applied_coupon_code)
            applied_discount = applied_coupon.calculate_discount(subtotal)
        else:
            applied_discount = Decimal('0.00')
        taxable = (subtotal - applied_discount)
        if taxable < Decimal('0.00'):
            taxable = Decimal('0.00')
        tax_amount = (taxable * Decimal('0.05')).quantize(Decimal('0.01'))
        delivery_fee = Decimal('20.00')
        # Waive delivery for FREESHIP on orders >= 1000
        try:
            if applied_coupon_code and applied_coupon_code.upper() == 'FREESHIP' and subtotal >= Decimal('1000'):
                delivery_fee = Decimal('0.00')
        except Exception:
            pass
        grand_total = (taxable + tax_amount + delivery_fee).quantize(Decimal('0.01'))
    except Exception:
        # Fallback to float math if Decimal not available in context
        subtotal = total
        disc = 0.0
        tax_base = max(subtotal - disc, 0.0)
        tax_amount = round(tax_base * 0.05, 2)
        delivery_fee = 20.00
        grand_total = round(tax_base + tax_amount + delivery_fee, 2)
    addresses = UserAddress.objects.filter(user=request.user)
    categories = Category.objects.all()
    cart_count = cart_items.count()

    if request.method == "POST" and request.POST.get('action') != 'apply_coupon':
        address_id = request.POST.get('address')
        if address_id:
            address = UserAddress.objects.get(id=address_id, user=request.user)
        else:
            address = None
        
        # Old immediate placement path kept for fallback, but prefer PayPal flow
        messages.info(request, "Please use the PayPal button to complete payment.")
        return redirect('checkout')

    # Pull active coupons to show in the view list
    from .models import Coupon
    from django.utils import timezone
    coupons = Coupon.objects.filter(is_active=True, valid_from__lte=timezone.now(), valid_until__gte=timezone.now())

    return render(request, 'store/checkout.html', {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'tax_amount': tax_amount,
        'grand_total': grand_total,
        'discount': applied_discount,
        'applied_coupon': applied_coupon,
        'delivery_fee': delivery_fee,
        'total': total,  # kept for backward compatibility if template references it
        'coupons': coupons,
        'addresses': addresses,
        'categories': categories,
        'cart_count': cart_count,
    })


@login_required
def checkout_success(request):
    categories = Category.objects.all()
    cart_count = CartItem.objects.filter(user=request.user).count()
    # Try to fetch the most recent order(s) placed in this session
    orders = []
    primary_order = None
    try:
        ids = request.session.get('recent_order_ids') or []
        if ids:
            orders = list(Order.objects.filter(user=request.user, id__in=ids).order_by('-created_at'))
            primary_order = orders[0] if orders else None
    except Exception:
        primary_order = None

    # Fallback to last order by user if session missing
    if not primary_order:
        primary_order = Order.objects.filter(user=request.user).order_by('-created_at').first()

    agent = None
    store = None
    eta_text = None
    eta_window = None
    if primary_order:
        try:
            assign = getattr(primary_order, 'delivery_assignment', None)
            if assign:
                agent = assign.agent
                store = agent.store_location if agent and agent.store_location else None
                if assign.expected_delivery_date:
                    eta_text = assign.expected_delivery_date.strftime('%d %b %Y')
        except Exception:
            pass

    # Fallbacks when assignment/agent/store missing: compute nearest store from order address
    if primary_order and (not store or not agent):
        addr = primary_order.address
        try:
            qs = StoreLocation.objects.filter(is_active=True)
            # Prefer city match
            st = None
            if addr and addr.city:
                st = qs.filter(city__iexact=addr.city).first()
            if not st:
                st = qs.first()
            if not store:
                store = st
            if not agent and store:
                # Prefer available at that store, then any active at that store
                agent = DeliveryAgent.objects.filter(is_active=True, is_available=True, store_location=store).first() or \
                        DeliveryAgent.objects.filter(is_active=True, store_location=store).first()
        except Exception:
            pass

    return render(request, 'store/checkout_success.html', {
        'categories': categories,
        'cart_count': cart_count,
        'primary_order': primary_order,
        'delivery_agent': agent,
        'nearest_store': store,
        'eta_text': eta_text,
        'eta_window': eta_window,
    })


@login_required
def coupons_list(request):
    from .models import Coupon
    from django.utils import timezone
    coupons = Coupon.objects.filter(is_active=True, valid_from__lte=timezone.now(), valid_until__gte=timezone.now())
    next_url = request.GET.get('next') or 'checkout'
    categories = Category.objects.all()
    cart_count = CartItem.objects.filter(user=request.user).count()
    return render(request, 'store/coupons.html', {
        'coupons': coupons,
        'next': next_url,
        'categories': categories,
        'cart_count': cart_count,
    })


@login_required
def apply_coupon(request):
    """Validate and apply a coupon, then redirect back to `next` (default checkout)."""
    next_url = request.GET.get('next') or request.POST.get('next') or 'checkout'
    code = (request.GET.get('code') or request.POST.get('coupon_code') or '').strip()
    if not code:
        messages.info(request, 'Coupon removed')
        request.session.pop('applied_coupon_code', None)
        return redirect(next_url)

    try:
        from .models import Coupon
        from decimal import Decimal
        # Compute current cart subtotal
        cart_items = CartItem.objects.filter(user=request.user)
        subtotal = Decimal(str(sum(item.total_price() for item in cart_items)))
        c = Coupon.objects.get(code__iexact=code)
        ok, msg = c.can_be_used_by_user(request.user, subtotal)
        if ok:
            request.session['applied_coupon_code'] = c.code
            discount_amt = c.calculate_discount(subtotal)
            # Special handling notice for FREESHIP is naturally reflected at checkout via delivery fee 0
            messages.success(request, f"Coupon '{c.code}' applied: Rs. {discount_amt}")
        else:
            request.session.pop('applied_coupon_code', None)
            messages.error(request, msg or 'Invalid coupon')
    except Coupon.DoesNotExist:
        request.session.pop('applied_coupon_code', None)
        messages.error(request, 'Invalid coupon code')
    return redirect(next_url)


@login_required
def add_address(request):
    categories = Category.objects.all()
    cart_count = CartItem.objects.filter(user=request.user).count()
    
    if request.method == 'POST':
        address = UserAddress.objects.create(
            user=request.user,
            address_line1=request.POST['address_line1'],
            address_line2=request.POST.get('address_line2', ''),
            city=request.POST['city'],
            state=request.POST['state'],
            postal_code=request.POST['postal_code'],
            country=request.POST.get('country', 'India'),
            is_default=request.POST.get('is_default') == 'on'
        )
        messages.success(request, 'Address added successfully!')
        return redirect('profile')
    
    return render(request, 'store/add_address.html', {
        'categories': categories,
        'cart_count': cart_count,
    })


@login_required
def delete_address(request, pk):
    address = get_object_or_404(UserAddress, pk=pk, user=request.user)
    address.delete()
    messages.success(request, 'Address deleted successfully!')
    return redirect('profile')


@login_required
def download_invoice(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    # Create PDF
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Branding Header
    top_y = height - 50
    # Try to draw logo if available
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'store', 'logo.png')
    if os.path.exists(logo_path):
        try:
            p.drawImage(logo_path, 50, top_y - 40, width=80, height=30, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass
    p.setFont("Helvetica-Bold", 20)
    p.drawRightString(width - 50, top_y - 10, "INVOICE")

    # Seller Details
    y = top_y - 60
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "GourmetGrove")
    p.setFont("Helvetica", 10)
    y -= 14; p.drawString(50, y, "123 Sweet Lane, Chocolate City, India")
    y -= 14; p.drawString(50, y, "Email: support@themunchloom.in")
    y -= 14; p.drawString(50, y, "Phone: +91-98765-43210")
    y -= 14; p.drawString(50, y, "GSTIN: 27ABCDE1234F1Z5")

    # Buyer Details
    y -= 26
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Bill To:")
    p.setFont("Helvetica", 10)
    y -= 14; p.drawString(50, y, f"{order.user.get_full_name() or order.user.username}")
    if order.address:
        addr_line = order.address.address_line1
        if order.address.address_line2:
            addr_line += f", {order.address.address_line2}"
        city_line = f"{order.address.city}, {order.address.state} {order.address.postal_code}"
        y -= 14; p.drawString(50, y, addr_line)
        y -= 14; p.drawString(50, y, city_line)
    # Contact details
    if getattr(order.user, 'email', None):
        y -= 14; p.drawString(50, y, f"Email: {order.user.email}")
    try:
        profile = UserProfile.objects.get(user=order.user)
        if profile.phone_number:
            y -= 14; p.drawString(50, y, f"Phone: {profile.phone_number}")
    except UserProfile.DoesNotExist:
        pass

    # Invoice Details
    right_x = width - 50
    info_y = top_y - 60
    p.setFont("Helvetica-Bold", 12)
    p.drawRightString(right_x, info_y, f"Invoice No: {order.invoice_number}")
    p.setFont("Helvetica", 10)
    info_y -= 14; p.drawRightString(right_x, info_y, f"Order ID: ORD-{order.id}")
    info_y -= 14; p.drawRightString(right_x, info_y, f"Invoice Date: {order.created_at.strftime('%d/%m/%Y')}")
    info_y -= 14; p.drawRightString(right_x, info_y, f"Payment Mode: Online")

    # Divider line
    y -= 16
    p.line(50, y, width - 50, y)
    y -= 20

    # Order Summary Table Header
    p.setFont("Helvetica-Bold", 11)
    col_x = [50, 90, 300, 360, 430, 510]
    headers = ["Sl. No", "Product Name", "Qty", "Unit Price", "Total Price"]
    # Adjust columns: using 5 columns -> redefine col_x accordingly
    col_x = [50, 100, 370, 440, 520]
    for i, htxt in enumerate(headers):
        x = col_x[i]
        p.drawString(x, y, htxt)
    y -= 14
    p.line(50, y, width - 50, y)
    y -= 12

    # Single-line item (current model supports one product per order)
    p.setFont("Helvetica", 10)
    sl = 1
    name = order.chocolate.name
    qty = order.quantity
    unit_price = order.chocolate.price
    line_total = order.subtotal()
    p.drawString(col_x[0], y, str(sl))
    p.drawString(col_x[1], y, name[:40])
    p.drawRightString(col_x[2]+10, y, str(qty))
    p.drawRightString(col_x[3]+30, y, f"Rs. {unit_price:.2f}")
    p.drawRightString(col_x[4]+30, y, f"Rs. {line_total:.2f}")
    y -= 18

    # Totals
    p.line(50, y, width - 50, y)
    y -= 10

    # Compute amounts
    subtotal = Decimal(order.subtotal())
    # Shipping: flat Rs. 20
    shipping_fee = Decimal('20.00')
    # Discount via coupon usage if any
    from .models import CouponUsage
    try:
        cu = CouponUsage.objects.get(order=order)
        discount = Decimal(cu.discount_amount)
        discount_label = f"Discount ({cu.coupon.code})"
    except CouponUsage.DoesNotExist:
        discount = Decimal('0.00')
        discount_label = "Discount"
    # GST 5% on (subtotal - discount)
    taxable = max(subtotal - discount, Decimal('0.00'))
    tax_rate = Decimal('0.05')
    tax = (taxable * tax_rate).quantize(Decimal('0.01'))
    grand_total = (taxable + shipping_fee + tax).quantize(Decimal('0.01'))

    label_x = col_x[3]-40
    value_x = col_x[4]+30

    p.setFont("Helvetica", 10)
    p.drawRightString(label_x, y, "Subtotal:")
    p.drawRightString(value_x, y, f"Rs. {subtotal:.2f}")
    y -= 14
    p.drawRightString(label_x, y, "Shipping:")
    p.drawRightString(value_x, y, f"Rs. {shipping_fee:.2f}")
    y -= 14
    p.drawRightString(label_x, y, f"{discount_label}:")
    p.drawRightString(value_x, y, f"-Rs. {discount:.2f}")
    y -= 14
    p.drawRightString(label_x, y, "Tax (GST 5%):")
    p.drawRightString(value_x, y, f"Rs. {tax:.2f}")
    y -= 16
    p.setFont("Helvetica-Bold", 12)
    p.drawRightString(label_x, y, "Grand Total:")
    p.drawRightString(value_x, y, f"Rs. {grand_total:.2f}")

    # Notes
    y -= 28
    p.setFont("Helvetica", 9)
    p.drawString(50, y, "Thank you for shopping at GourmetGrove!")
    y -= 12; p.drawString(50, y, "For returns or refunds, please refer to our Return Policy.")
    y -= 12; p.drawString(50, y, "Need help? Contact us at support@themunchloom.in or +91-98765-43210")

    # Footer motto
    p.setFont("Helvetica-Oblique", 9)
    p.drawCentredString(width/2, 40, "GourmetGrove – Where Every Bite is a Sweet Memory")
    
    p.showPage()
    p.save()
    
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    # Force download as attachment
    response['Content-Disposition'] = f'attachment; filename="invoice_{order.invoice_number}.pdf"'
    response['Cache-Control'] = 'no-store'
    return response


@login_required
def add_review(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    if request.method == 'POST':
        rating = request.POST.get('rating')
        comment = request.POST.get('comment', '')
        
        if rating:
            review, created = Review.objects.get_or_create(
                user=request.user,
                chocolate=order.chocolate,
                order=order,
                defaults={
                    'rating': rating,
                    'comment': comment
                }
            )
            
            if not created:
                review.rating = rating
                review.comment = comment
                review.save()
            
            messages.success(request, 'Review submitted successfully!')
            return redirect('product_detail', pk=order.chocolate.pk)
    
    return redirect('product_detail', pk=order.chocolate.pk)





# ✅ Custom Login View with success message
class CustomLoginView(LoginView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        return context
    
    def form_valid(self, form):
        messages.success(self.request, 'Login successful!')
        return super().form_valid(form)


# ✅ Custom logout if needed (not required if using LogoutView with next_page)
def custom_logout(request):
    logout(request)
    return redirect('home')


# Policy Pages
def about_us(request):
    """About Us page"""
    return render(request, 'store/about_us.html', {
        'categories': Category.objects.all(),
        'cart_count': CartItem.objects.filter(user=request.user).count() if request.user.is_authenticated else 0,
    })


def privacy_policy(request):
    """Privacy Policy page"""
    return render(request, 'store/privacy_policy.html', {
        'categories': Category.objects.all(),
        'cart_count': CartItem.objects.filter(user=request.user).count() if request.user.is_authenticated else 0,
    })


def terms_of_use(request):
    """Terms of Use page"""
    return render(request, 'store/terms_of_use.html', {
        'categories': Category.objects.all(),
        'cart_count': CartItem.objects.filter(user=request.user).count() if request.user.is_authenticated else 0,
    })


def shipping_policy(request):
    """Shipping Policy page"""
    return render(request, 'store/shipping_policy.html', {
        'categories': Category.objects.all(),
        'cart_count': CartItem.objects.filter(user=request.user).count() if request.user.is_authenticated else 0,
    })


def return_policy(request):
    """Return Policy page"""
    return render(request, 'store/return_policy.html', {
        'categories': Category.objects.all(),
        'cart_count': CartItem.objects.filter(user=request.user).count() if request.user.is_authenticated else 0,
    })

def contact(request):
    """Contact Us page"""
    return render(request, 'store/contact.html', {
        'categories': Category.objects.all(),
        'cart_count': CartItem.objects.filter(user=request.user).count() if request.user.is_authenticated else 0,
    })

@csrf_exempt
@require_http_methods(["POST"])
def chatbot_api(request):
    """
    API endpoint for the chatbot to process user messages and return responses.
    """
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').lower()
        
        # Initialize response
        response = {
            'status': 'success',
            'message': '',
            'suggestions': []
        }
        
        # Common greetings and responses
        greetings = ['hi', 'hello', 'hey', 'greetings', 'hola']
        farewells = ['bye', 'goodbye', 'see you', 'farewell']
        thanks = ['thanks', 'thank you', 'appreciate it']
        
        # Check for greetings
        if any(greeting in user_message for greeting in greetings):
            response['message'] = random.choice([
                "Hello! How can I assist you today?",
                "Hi there! How can I help you with your chocolate journey?",
                "Greetings! What can I do for you today?"
            ])
            response['suggestions'] = [
                "What products do you have?",
                "How can I track my order?",
                "What are your shipping policies?"
            ]
        
        # Check for farewells
        elif any(farewell in user_message for farewell in farewells):
            response['message'] = random.choice([
                "Goodbye! Come back soon for more chocolatey goodness! 🍫",
                "Thank you for visiting GourmetGrove! Have a sweet day! 🍫",
                "See you later! Don't forget to treat yourself to some chocolate!"
            ])
        
        # Check for thanks
        elif any(thank in user_message for thank in thanks):
            response['message'] = random.choice([
                "You're welcome! Is there anything else I can help you with?",
                "My pleasure! Let me know if you need anything else.",
                "Happy to help! What else would you like to know?"
            ])
        
        # Product related queries
        elif any(keyword in user_message for keyword in ['product', 'chocolate', 'candy', 'treat']):
            response['message'] = "We offer a wide variety of premium chocolates including dark, milk, and white chocolate. Is there a specific type you're interested in?"
            response['suggestions'] = [
                "Show me dark chocolates",
                "What's new in your collection?",
                "What are your bestsellers?"
            ]
        
        # Order tracking
        elif any(keyword in user_message for keyword in ['track', 'tracking', 'order status', 'where is my order']):
            response['message'] = "To track your order, please go to 'My Account' > 'Orders' and click on your order number. You'll find the tracking information there."
            response['suggestions'] = [
                "How do I create an account?",
                "What's your return policy?",
                "Contact customer service"
            ]
        
        # Shipping information
        elif any(keyword in user_message for keyword in ['shipping', 'delivery', 'how long', 'when will it arrive']):
            response['message'] = "We offer various shipping options:"
            response['message'] += "\n• Standard: 3-5 business days"
            response['message'] += "\n• Express: 1-2 business days"
            response['message'] += "\n• Same-day delivery available in select areas"
            response['suggestions'] = [
                "What's your return policy?",
                "Do you ship internationally?",
                "How much is shipping?"
            ]
        
        # Default response if no specific intent is matched
        else:
            response['message'] = "I'm here to help! Could you please rephrase your question or choose from these options?"
            response['suggestions'] = [
                "What products do you have?",
                "How can I track my order?",
                "What are your shipping policies?",
                "Contact customer service"
            ]
        
        return JsonResponse(response)
    
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': 'Sorry, I encountered an error processing your request. Please try again later.'
        }, status=500)
