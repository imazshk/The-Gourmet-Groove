// Main JavaScript file for GourmetGrove

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Handle mobile menu toggle
    const mobileMenuToggle = document.getElementById('mobileMenuToggle');
    const mobileMenu = document.getElementById('mobileMenu');
    
    if (mobileMenuToggle && mobileMenu) {
        mobileMenuToggle.addEventListener('click', function(e) {
            e.preventDefault();
            mobileMenu.classList.toggle('show');
            this.setAttribute('aria-expanded', 
                this.getAttribute('aria-expanded') === 'true' ? 'false' : 'true'
            );
        });
    }

    // Handle cart quantity changes
    const quantityInputs = document.querySelectorAll('.quantity-input');
    quantityInputs.forEach(input => {
        input.addEventListener('change', function() {
            const form = this.closest('form');
            if (form) form.submit();
        });
    });

    // Handle AJAX add to cart
    const addToCartForms = document.querySelectorAll('.add-to-cart-form');
    addToCartForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            
            fetch(this.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': formData.get('csrfmiddlewaretoken')
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Update cart count
                    const cartCount = document.querySelector('.cart-count');
                    if (cartCount) {
                        cartCount.textContent = data.cart_count;
                    }
                    
                    // Show success message
                    showToast('Success', 'Item added to cart!', 'success');
                } else {
                    showToast('Error', data.message || 'Failed to add item to cart', 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showToast('Error', 'An error occurred. Please try again.', 'error');
            });
        });
    });

    // Toast notification function
    function showToast(title, message, type = 'info') {
        const toastContainer = document.getElementById('toastContainer');
        if (!toastContainer) return;
        
        const toast = document.createElement('div');
        toast.className = `toast show align-items-center text-white bg-${type} border-0`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <strong>${title}</strong><br>${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        `;
        
        toastContainer.appendChild(toast);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 150);
        }, 5000);
    }

    // Handle tab visibility changes
    const originalTitle = document.title || 'GourmetGrove';
    const messages = [
        '🍫 Don\'t forget about your cart!',
        '✨ New chocolates just in!',
        '🎁 Special offers waiting!' 
    ];
    let ticker = null;
    let messageIndex = 0;

    function startTicker() {
        if (ticker) return;
        messageIndex = 0;
        updateTitle();
        ticker = setInterval(updateTitle, 2000);
    }

    function stopTicker() {
        if (ticker) {
            clearInterval(ticker);
            ticker = null;
        }
        document.title = originalTitle;
    }

    function updateTitle() {
        document.title = messages[messageIndex] + ' | ' + originalTitle;
        messageIndex = (messageIndex + 1) % messages.length;
    }

    function handleVisibility() {
        if (document.hidden) {
            startTicker();
        } else {
            stopTicker();
        }
    }

    document.addEventListener('visibilitychange', handleVisibility);
    window.addEventListener('blur', startTicker);
    window.addEventListener('focus', stopTicker);

    // Initialize any datepickers
    if (typeof flatpickr !== 'undefined') {
        flatpickr('.datepicker', {
            dateFormat: 'Y-m-d',
            allowInput: true
        });
    }
});

// Utility function to format currency
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(amount);
}

// Update sort button text based on current selection
function updateSortButton() {
    const urlParams = new URLSearchParams(window.location.search);
    const sort = urlParams.get('sort') || 'name';
    const order = urlParams.get('order') || 'asc';
    const sortButton = document.getElementById('sortButton');
    
    if (sortButton) {
        sortButton.textContent = getSortDisplayText(sort, order);
    }
}

// Get display text for sort options
function getSortDisplayText(sort, order) {
    const sortTexts = {
        'name': 'Name',
        'price': 'Price',
        'created_at': 'Newest',
        'rating': 'Rating'
    };
    
    const orderText = order === 'asc' ? ' (A-Z)' : ' (Z-A)';
    return (sortTexts[sort] || 'Sort by') + (sort !== 'price' ? orderText : '');
}

// Initialize any components that need it
if (typeof bootstrap !== 'undefined') {
    // Initialize any Bootstrap components here if needed
    const toastElList = [].slice.call(document.querySelectorAll('.toast'));
    const toastList = toastElList.map(function (toastEl) {
        return new bootstrap.Toast(toastEl, { autohide: true, delay: 5000 });
    });
}
