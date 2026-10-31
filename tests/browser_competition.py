"""Workspace checks after browser_ui.py has solved the preview challenge."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from browser_ui import BASE, login


with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True)
    player = browser.new_page(viewport={'width': 390, 'height': 844})
    admin = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors = []
    player.on('pageerror', lambda error: errors.append(str(error)))
    admin.on('pageerror', lambda error: errors.append(str(error)))
    login(player, 'preview-player')
    expect(player.locator('.competition-strip')).to_have_count(0)
    expect(player.locator('link[rel=icon]')).to_have_attribute('href', '/static/images/cyscom-logo.webp')
    player.select_option('#categoryFilter', 'Web')
    expect(player.locator('#challengeResults')).to_have_text('1 of 1 challenges')
    player.check('#unsolvedFilter')
    expect(player.locator('#noChallengeMatches')).to_be_visible()
    player.click('#clearFilters')
    expect(player.locator('.challenge-entry')).to_be_visible()
    assert player.evaluate('document.documentElement.scrollWidth <= innerWidth')
    player.screenshot(path='artifacts/ui/challenges-mobile.png', full_page=True)
    player.click('.navbar-toggler')
    player.click('#notificationsDropdown')
    expect(player.locator('#notifList')).to_be_visible()
    login(admin, 'preview-admin')
    player.goto(BASE + '/scoreboard/')
    player.select_option('#standingsView', 'nearby')
    expect(player.locator('.own-standing')).to_contain_text('Packet Inspectors')
    expect(player.locator('.first-blood')).to_contain_text('1 first blood')
    admin.goto(BASE + '/admin/settings')
    admin.check('#scoreboard_frozen')
    admin.locator('form[action$="/settings/event-config"] button[type="submit"]').click()
    expect(player.locator('#freezeNotice')).to_be_visible(timeout=20000)
    expect(player.locator('#scoreboardStatus')).to_be_hidden()
    expect(player.locator('.standings-summary')).to_have_count(0)
    assert player.locator('.leaderboard-stage').evaluate('(el) => getComputedStyle(el).backgroundColor') == 'rgb(21, 31, 46)'
    expect(player.locator('.leaderboard-mark')).to_be_visible()
    player.screenshot(path='artifacts/ui/standings-frozen-mobile.png', full_page=True)
    admin.goto(BASE + '/scoreboard/')
    expect(admin.locator('#freezeNotice')).to_contain_text('live admin standings')
    admin.goto(BASE + '/admin/settings')
    admin.uncheck('#scoreboard_frozen')
    admin.locator('form[action$="/settings/event-config"] button[type="submit"]').click()
    expect(player.locator('#freezeNotice')).to_be_hidden(timeout=20000)
    assert not errors, errors
    browser.close()
    print('PASS: category/unsolved filters, navbar announcements and favicon, own rank, first blood, freeze and unfreeze.')
