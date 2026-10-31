import re
import unittest
from datetime import datetime, timedelta
from flask import url_for
from tests.ui_fixture import seed, app, Settings


class UIFlows(unittest.TestCase):
    def setUp(self):
        seed()
        self.client = app.test_client()

    def token(self, path='/login'):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, path)
        return re.search(r'name="csrf-token" content="([^"]+)"', response.text).group(1)

    def login(self, admin=False):
        response = self.client.post('/login', data={'username': 'preview-admin' if admin else 'preview-player', 'password': 'PreviewOnly123!', 'csrf_token': self.token()})
        self.assertEqual(response.status_code, 302)

    def test_public_pages_and_assets(self):
        for path in ['/', '/login', '/register', '/forgot-password', '/about', '/static/js/theme.js', '/static/js/app.js', '/static/js/notifications.js', '/static/js/scoreboard.js', '/static/css/design.css', '/static/images/cyscom-logo.webp', '/static/vendor/bootstrap.min.css']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        error_response = self.client.get('/requirements')
        self.assertEqual(error_response.status_code, 404)
        error_page = error_response.text
        self.assertIn('class="error-page text-center py-5"', error_page)
        self.assertIn('background:rgb(var(--panel-rgb))', self.client.get('/static/css/design.css').text)
        home = self.client.get('/').text
        self.assertNotIn('themeSelect', home)
        self.assertNotIn('github.com', home)
        self.assertNotIn('discipline-list', home)
        for path in ['/scoreboard/', '/scoreboard/api/data', '/scoreboard/api/top/3']:
            self.assertEqual(self.client.get(path).status_code, 302)
        for name in app.jinja_env.list_templates():
            app.jinja_env.get_template(name)

    def test_player_pages(self):
        self.login()
        for path in ['/', '/challenges/', '/challenges/1', '/profile', '/teams/', '/teams/1', '/teams/create', '/teams/join', '/scoreboard/', '/api/notifications']:
            with self.subTest(path=path):
                response = self.client.get(path, follow_redirects=True)
                self.assertEqual(response.status_code, 200, response.text[:200])

    def test_admin_pages(self):
        self.login(admin=True)
        endpoints = ['admin.dashboard', 'admin.manage_challenges', 'admin.create_challenge', 'admin.manage_branching', 'admin.manage_users', 'admin.manage_teams', 'admin.manage_notifications', 'admin.flag_abuse', 'admin.hint_logs', 'admin.backups', 'admin.settings']
        with app.test_request_context():
            paths = [url_for(endpoint) for endpoint in endpoints]
        for path in paths + ['/admin/challenges/1/edit']:
            with self.subTest(path=path):
                response = self.client.get(path, follow_redirects=True)
                self.assertEqual(response.status_code, 200, response.text[:200])
                if path == '/admin/settings':
                    self.assertEqual(response.text.count('const examples ='), 1)

    def test_flag_and_hint_requests_accept_csrf(self):
        self.login()
        token = self.token('/challenges/1')
        headers = {'X-CSRF-Token': token}
        response = self.client.post('/hints/1/unlock', headers=headers)
        self.assertTrue(response.json['success'], response.json)
        response = self.client.post('/challenges/1/submit', data={'flag': 'incorrect'}, headers=headers)
        self.assertFalse(response.json['success'])
        from services.cache import cache_service
        cache_service.redis_client.delete('solve_lock:1:1')
        response = self.client.post('/challenges/1/submit', data={'flag': 'CYSCOM{local_preview}'}, headers=headers)
        self.assertTrue(response.json['success'], response.json)
        self.assertEqual(self.client.get('/scoreboard/api/data').json[0]['score'], 100)

    def test_countdown_and_event_status(self):
        self.login()
        with app.app_context():
            Settings.set('ctf_start_time', datetime.utcnow() + timedelta(hours=1), 'datetime')
        self.assertFalse(self.client.get('/api/event-status').json['started'])
        response = self.client.get('/scoreboard/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('/api/event-status', response.text)

    def test_leaderboard_visibility_applies_to_rest_and_live_updates(self):
        self.login()
        from services.websocket import socketio, WebSocketService
        with app.app_context():
            Settings.set('scoreboard_visible', False, 'bool')
        self.assertEqual(self.client.get('/scoreboard/api/data').json, [])
        self.assertEqual(self.client.get('/scoreboard/api/top/3').json, [])
        # Exercise the socket handler with the same Flask login contexts as transport clients.
        from unittest.mock import patch
        from services.websocket import handle_request_scoreboard
        from flask_login import login_user
        from models.user import User
        with app.test_request_context(), patch('services.websocket.emit') as emit:
            handle_request_scoreboard()
            emit.assert_called_once_with('scoreboard_update', [])
        self.client.get('/logout')
        self.login(admin=True)
        self.assertEqual(len(self.client.get('/scoreboard/api/data').json), 1)
        with app.test_request_context(), patch('services.websocket.emit') as emit:
            login_user(User.query.filter_by(is_admin=True).first())
            handle_request_scoreboard()
            self.assertEqual(len(emit.call_args.args[1]), 1)
        with app.app_context(), patch.object(socketio, 'emit') as emit:
            WebSocketService.emit_scoreboard_update([{'name': 'Private ranking'}])
            self.assertEqual(emit.call_args.kwargs.get('to'), 'scoreboard_admin')

    def test_top_rankings_do_not_truncate_the_full_leaderboard(self):
        self.login()
        from models import db
        from models.team import Team
        with app.app_context():
            db.session.add(Team(name='Second team', invite_code='SECOND12'))
            db.session.commit()
        self.assertEqual(len(self.client.get('/scoreboard/api/top/1').json), 1)
        self.assertEqual(len(self.client.get('/scoreboard/api/data').json), 2)

    def test_notification_read_action(self):
        from models import db
        from models.notification import Notification
        with app.app_context():
            notification = Notification(title='Event notice', body='Challenge updated.')
            db.session.add(notification)
            db.session.commit()
        self.login()
        self.assertEqual(self.client.get('/api/notifications').json['unread'], 1)
        result = self.client.post('/api/notifications/1/read', headers={'X-CSRF-Token': self.token('/profile')})
        self.assertTrue(result.json['success'])
        self.assertEqual(self.client.get('/api/notifications').json['unread'], 0)

    def test_admin_theme_and_logo_can_be_saved_locally(self):
        from io import BytesIO
        from tempfile import TemporaryDirectory
        self.login(admin=True)
        response = self.client.post('/admin/settings/background-theme', data={
            'site_theme': 'forest',
            'custom_background_enabled': 'on',
            'custom_background_css': 'body { background-color: var(--canvas); }',
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        with app.app_context():
            self.assertTrue(Settings.get('custom_background_enabled', type='bool'))
            self.assertEqual(Settings.get('site_theme'), 'forest')
        self.assertIn('id="adminThemeSelect"', response.text)
        visitor = app.test_client()
        visitor_home = visitor.get('/')
        self.assertIn('data-theme="forest"', visitor_home.text)
        self.assertIn('data-custom-background="true"', visitor_home.text)
        self.assertIn('class="technology-background"', visitor_home.text)
        self.assertNotIn('adminThemeSelect', visitor.get('/').text)
        with TemporaryDirectory(dir='uploads') as folder:
            old_folder = app.config['LOGO_UPLOAD_FOLDER']
            app.config['LOGO_UPLOAD_FOLDER'] = folder
            try:
                response = self.client.post('/admin/settings/event-config', data={
                    'ctf_name': 'Local event', 'scoreboard_visible': 'on',
                    'ctf_logo': (BytesIO(b'local-logo-content'), 'logo.png'),
                }, content_type='multipart/form-data', follow_redirects=True)
                self.assertEqual(response.status_code, 200)
                with app.app_context():
                    filename = Settings.get('ctf_logo')
                self.assertTrue(filename)
                self.assertEqual(self.client.get('/uploads/' + filename).data, b'local-logo-content')
            finally:
                app.config['LOGO_UPLOAD_FOLDER'] = old_folder

    def test_player_cannot_change_the_site_theme(self):
        self.login()
        response = self.client.post('/admin/settings/background-theme', data={'site_theme': 'paper'})
        self.assertEqual(response.status_code, 302)
        with app.app_context():
            self.assertEqual(Settings.get('site_theme', 'default'), 'default')
        self.assertNotIn('adminThemeSelect', self.client.get('/').text)



if __name__ == '__main__':
    unittest.main()


class SubmissionChallengeTypeUI(unittest.TestCase):
    setUp = UIFlows.setUp
    token = UIFlows.token
    login = UIFlows.login
    def test_submission_challenge_type_filters_export_and_pagination(self):
        from models import db
        from models.challenge import Challenge
        from models.submission import Submission
        with app.app_context():
            db.session.get(Challenge, 1).is_dynamic = True
            dynamic = Challenge(name='Dynamic example', description='test', category='Web', flag='test', is_dynamic=False, docker_enabled=True)
            db.session.add(dynamic)
            db.session.flush()
            for i in range(52):
                db.session.add(Submission(user_id=2, challenge_id=1, submitted_flag='test', is_correct=False))
            db.session.add(Submission(user_id=1, challenge_id=dynamic.id, submitted_flag='dynamic', is_correct=True))
            db.session.commit()
        self.login(admin=True)
        page = self.client.get('/admin/submissions?page=2&challenge_type=static')
        self.assertEqual(page.status_code, 200)
        self.assertIn('Static</button>', page.text)
        self.assertNotIn('Dynamic</button>', page.text)
        filtered = self.client.get('/admin/submissions?challenge_type=dynamic')
        self.assertIn('Dynamic</button>', filtered.text)
        export = self.client.get('/admin/submissions/export?challenge_type=dynamic&user_id=2')
        self.assertEqual(len(export.text.strip().splitlines()), 1)
        export = self.client.get('/admin/submissions/export?challenge_type=dynamic&user_id=1')
        self.assertIn('Challenge Type', export.text)
        self.assertIn('Dynamic', export.text)
        self.assertEqual(len(export.text.strip().splitlines()), 2)
        self.client.get('/logout')
        self.login()
        self.assertEqual(self.client.get('/admin/submissions').status_code, 302)
