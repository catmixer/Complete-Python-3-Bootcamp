/* Health Tracker - Core JavaScript */

// API helper
async function api(endpoint, options = {}) {
    const defaults = {
        headers: { 'Content-Type': 'application/json' },
    };
    if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
        options.body = JSON.stringify(options.body);
    }
    if (options.body instanceof FormData) {
        delete defaults.headers['Content-Type'];
    }
    const resp = await fetch(endpoint, { ...defaults, ...options });
    return resp.json();
}

// Check if profile exists, redirect to setup if not
async function checkProfile() {
    try {
        const resp = await fetch('/api/user/profile');
        if (resp.status === 404 && window.location.pathname !== '/') {
            window.location.href = '/';
        }
    } catch (e) {
        // Server might not be running
    }
}

// Run on all pages except index
if (window.location.pathname !== '/') {
    checkProfile();
}
