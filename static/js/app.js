function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]')?.content || '';
}
function fetchWithCSRF(url, options = {}) {
    const headers = new Headers(options.headers || {});
    const method = (options.method || 'GET').toUpperCase();
    if (new URL(url, location.href).origin === location.origin && !['GET', 'HEAD', 'OPTIONS'].includes(method)) {
        headers.set('X-CSRF-Token', getCSRFToken());
    }
    return fetch(url, { ...options, headers });
}
function escapeHtml(value) {
    const element = document.createElement('span');
    element.textContent = String(value ?? '');
    return element.innerHTML;
}
function addFormTokens() {
    document.querySelectorAll('form').forEach(form => {
        if (form.method.toLowerCase() !== 'post' || form.querySelector('[name="csrf_token"]')) return;
        const input = document.createElement('input');
        input.type = 'hidden'; input.name = 'csrf_token'; input.value = getCSRFToken();
        form.appendChild(input);
    });
}
document.addEventListener('DOMContentLoaded', () => {
    addFormTokens();
    document.addEventListener('submit', addFormTokens, true);
    document.querySelectorAll('.navbar a.nav-link').forEach(link => {
        if (link.getAttribute('href') === location.pathname) link.setAttribute('aria-current', 'page');
    });
});

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-bs-toggle="popover"]').forEach(element => {
        new bootstrap.Popover(element, { container: 'body' });
    });
});
