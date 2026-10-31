/* The administrator's saved palette applies to everyone. No participant preference. */
window.BlackBoxThemes = (() => {
    const names = ['default', 'graphite', 'forest', 'copper', 'paper'];
    const normalize = value => value === 'light' ? 'paper' : names.includes(value) ? value : 'default';
    const apply = value => {
        const theme = normalize(value);
        document.documentElement.dataset.theme = theme;
        document.documentElement.dataset.bsTheme = theme === 'paper' ? 'light' : 'dark';
        const selector = document.getElementById('adminThemeSelect');
        if (selector) selector.value = theme;
        return theme;
    };
    apply(document.documentElement.dataset.theme);
    document.addEventListener('DOMContentLoaded', () => {
        const selector = document.getElementById('adminThemeSelect');
        if (!selector) return;
        selector.value = document.documentElement.dataset.theme;
        selector.addEventListener('change', () => {
            apply(selector.value);
            document.getElementById('adminThemeNotice').textContent = 'Preview only. Save Background Theme to apply this palette to the whole site.';
        });
    });
    return { apply };
})();
