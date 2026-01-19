// Theme Toggle - Supports light, dark, and system preference
(function() {
    const THEME_KEY = 'theme-preference';

    // Get stored preference or default to 'system'
    function getStoredTheme() {
        return localStorage.getItem(THEME_KEY) || 'system';
    }

    // Apply theme to document
    function applyTheme(theme) {
        const root = document.documentElement;

        if (theme === 'system') {
            root.removeAttribute('data-theme');
        } else {
            root.setAttribute('data-theme', theme);
        }
    }

    // Cycle through themes: system -> light -> dark -> system
    function cycleTheme() {
        const current = getStoredTheme();
        let next;

        switch (current) {
            case 'system':
                next = 'light';
                break;
            case 'light':
                next = 'dark';
                break;
            case 'dark':
                next = 'system';
                break;
            default:
                next = 'system';
        }

        localStorage.setItem(THEME_KEY, next);
        applyTheme(next);
        updateToggleTitle(next);
    }

    // Update button title/tooltip
    function updateToggleTitle(theme) {
        const btn = document.getElementById('theme-toggle');
        if (btn) {
            const titles = {
                'system': 'Theme: System (click to change)',
                'light': 'Theme: Light (click to change)',
                'dark': 'Theme: Dark (click to change)'
            };
            btn.title = titles[theme] || titles['system'];
        }
    }

    // Initialize on page load
    function init() {
        const theme = getStoredTheme();
        applyTheme(theme);
        updateToggleTitle(theme);

        // Attach theme toggle click handler
        const btn = document.getElementById('theme-toggle');
        if (btn) {
            btn.addEventListener('click', cycleTheme);
        }

        // Mobile menu toggle
        const mobileMenuToggle = document.getElementById('mobile-menu-toggle');
        const navLinks = document.getElementById('nav-links');
        const navActions = document.getElementById('nav-actions');

        if (mobileMenuToggle && navLinks && navActions) {
            mobileMenuToggle.addEventListener('click', function() {
                navLinks.classList.toggle('active');
                navActions.classList.toggle('active');
            });

            // Close menu when clicking a link
            navLinks.querySelectorAll('a').forEach(function(link) {
                link.addEventListener('click', function() {
                    navLinks.classList.remove('active');
                    navActions.classList.remove('active');
                });
            });
        }
    }

    // Apply theme immediately to prevent flash
    applyTheme(getStoredTheme());

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
