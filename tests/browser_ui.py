"""Run against a fresh scripts/preview_ui.py instance using local Edge."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = os.environ.get('UI_BASE_URL', 'http://127.0.0.1:5050')


def login(page, name):
    page.goto(BASE + '/login')
    page.fill('#username', name)
    page.fill('#password', 'PreviewOnly123!')
    page.locator('button[type="submit"]').click()
    page.wait_for_url(BASE + ('/admin/' if name == 'preview-admin' else '/challenges/'))


def run():
    screenshots = Path('artifacts/ui')
    screenshots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        visitor = browser.new_context(viewport={'width':1440, 'height':1000})
        public = visitor.new_page()
        public.goto(BASE)
        assert public.locator('#themeSelect, #adminThemeSelect').count() == 0
        assert public.locator('footer a[href*="github"]').count() == 0
        assert public.locator('.discipline-list').count() == 0
        assert public.locator('footer, .desk-status').count() == 0
        assert public.locator('.nav-auth').count() == 2
        assert public.locator('.navbar').evaluate('(el) => getComputedStyle(el).backgroundColor') == 'rgba(0, 0, 0, 0)'
        assert public.locator('a[href="/requirements"]').count() == 0
        public.goto(BASE + '/scoreboard/')
        assert '/login?' in public.url
        assert 'Please log in to access this page.' not in public.locator('body').inner_text()
        for path in ['/scoreboard/api/data', '/scoreboard/api/top/3']:
            assert visitor.request.get(BASE + path, max_redirects=0).status == 302
        public.goto(BASE + '/about')
        assert public.locator('.accordion-button').first.bounding_box()['height'] >= 88
        for number in ['Two','Three','Four','Five','One']:
            public.locator(f'#heading{number} button').click()
            public.locator(f'#collapse{number}.show').wait_for()
        public.goto(BASE + '/about#how-to-play')
        public.locator('#collapseTwo.show').wait_for()
        public.screenshot(path=str(screenshots / 'about-graphite.png'), full_page=True)

        admin_context = browser.new_context(viewport={'width':1440,'height':1000})
        admin = admin_context.new_page()
        errors = []
        admin.on('pageerror', lambda error: errors.append(str(error)))
        login(admin, 'preview-admin')
        for theme in ['graphite','forest','copper','paper','default']:
            admin.goto(BASE + '/admin/settings')
            admin.select_option('#adminThemeSelect', theme)
            admin.check('#custom_background_enabled')
            admin.fill('#custom_background_css', 'body { background-color: var(--canvas); }')
            admin.locator('form[action$="/settings/background-theme"] button[type="submit"]').click()
            admin.reload()
            assert admin.locator('#adminThemeSelect').input_value() == theme
            public.goto(BASE)
            assert public.locator('html').get_attribute('data-theme') == theme
            assert public.locator('.technology-background').evaluate('(el) => getComputedStyle(el).display') != 'none'
            assert 'background.png' in public.locator('.technology-background').evaluate('(el) => getComputedStyle(el).backgroundImage')
            assert public.locator('#themeSelect, #adminThemeSelect').count() == 0
            public.screenshot(path=str(screenshots / f'home-{theme}.png'), full_page=True)
            admin.goto(BASE + '/scoreboard/')
            admin.wait_for_function("document.getElementById('scoreboardUpdated').textContent.startsWith('Updated')")
            admin.screenshot(path=str(screenshots / f'leaderboard-{theme}.png'), full_page=True)
        public.evaluate("localStorage.setItem('theme', 'paper')")
        public.reload()
        assert public.locator('html').get_attribute('data-theme') == 'default'
        public.set_viewport_size({'width':390,'height':844})
        for path, name in [('/', 'home-mobile'),('/about','about-mobile')]:
            public.goto(BASE + path)
            assert public.evaluate('document.documentElement.scrollWidth <= innerWidth')
            public.screenshot(path=str(screenshots / f'{name}.png'), full_page=True)

        player_context = browser.new_context(viewport={'width':1440,'height':1000})
        player = player_context.new_page()
        player.on('pageerror', lambda error: errors.append(str(error)))
        login(player, 'preview-player')
        for path in ['/','/challenges/','/challenges/1','/profile','/teams/','/teams/1','/about']:
            response = player.goto(BASE + path)
            assert response.status == 200
            assert player.locator('#themeSelect, #adminThemeSelect').count() == 0
        player.goto(BASE + '/challenges/1')
        player.fill('#flagInput','CYSCOM{local_preview}')
        player.click('#submitBtn')
        player.get_by_text('Points earned: 100', exact=False).wait_for()
        player.goto(BASE + '/scoreboard/')
        player.locator('#scoreboardBody').get_by_text('Packet Inspectors',exact=True).wait_for()
        assert player.locator('.score-cell').first.inner_text() == '100'
        # Confirm the original admin switch immediately removes an open participant board.
        player.wait_for_function("document.getElementById('scoreboardStatus').dataset.state === 'live'")
        admin.goto(BASE + '/admin/settings')
        admin.uncheck('#scoreboard_visible')
        admin.locator('form[action$="/settings/event-config"] button[type="submit"]').click()
        player.wait_for_url(BASE + '/')
        assert player.locator('a[href="/scoreboard/"]').count() == 0
        assert player_context.request.get(BASE + '/scoreboard/api/data').json() == []
        admin.goto(BASE + '/scoreboard/')
        admin.locator('#scoreboardBody').get_by_text('Packet Inspectors',exact=True).wait_for()
        admin.goto(BASE + '/admin/settings')
        admin.check('#scoreboard_visible')
        admin.locator('form[action$="/settings/event-config"] button[type="submit"]').click()
        player.goto(BASE + '/scoreboard/')
        player.locator('#scoreboardBody').get_by_text('Packet Inspectors',exact=True).wait_for()
        player.route('**/scoreboard/api/data',lambda route:route.fulfill(json=[]))
        player.click('#refreshScoreboard')
        player.get_by_text('No scores yet.',exact=False).wait_for()
        player.unroute('**/scoreboard/api/data')
        player.route('**/scoreboard/api/data',lambda route:route.fulfill(status=503,json={'error':'test'}))
        player.click('#refreshScoreboard')
        player.locator('#scoreboardUpdated').filter(has_text='Update failed').wait_for()
        assert player.locator('#refreshScoreboard').is_enabled()
        player.unroute('**/scoreboard/api/data')
        player.click('#refreshScoreboard')
        player.locator('#scoreboardBody').get_by_text('Packet Inspectors',exact=True).wait_for()
        player.set_viewport_size({'width':390,'height':844})
        player.click('.navbar-toggler')
        player.locator('#navbarNav.show').wait_for()
        assert player.evaluate('document.documentElement.scrollWidth <= innerWidth')
        player.screenshot(path=str(screenshots / 'leaderboard-mobile.png'), full_page=True)
        for path in ['/admin/','/admin/challenges','/admin/challenges/create','/admin/challenges/1/edit','/admin/users','/admin/teams','/admin/branching','/admin/settings','/admin/notifications','/admin/hint-logs','/admin/flag-abuse','/admin/backups','/admin/docker/status','/admin/docker/settings','/admin/dynamic-flags']:
            response = admin.goto(BASE + path)
            assert response.status == 200, f'{path}: {response.status}'
            admin.wait_for_timeout(100)
        assert not errors, json.dumps(errors,indent=2)
        browser.close()
        print('PASS: admin-only global themes, authenticated standings, immediate admin visibility toggle, photo background, home/about layouts, flag submission, mobile navigation, and admin scripts.')


if __name__ == '__main__':
    run()
