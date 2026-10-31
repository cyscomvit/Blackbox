import unittest
from datetime import datetime, timedelta
from tests.test_ui import UIFlows
from tests.ui_fixture import seed, app, Settings
from models import db
from models.submission import Solve
from models.team import Team
from services.standings import set_frozen
from services.cache import cache_service
from services.websocket import socketio, WebSocketService


class CompetitionWorkspace(unittest.TestCase):
    token = UIFlows.token
    login = UIFlows.login

    def setUp(self):
        seed()
        self.client = app.test_client()

    def test_freeze_http_socket_and_unfreeze(self):
        self.login()
        live = socketio.test_client(app, namespace='/live', flask_test_client=self.client)
        live.get_received('/live')
        with app.app_context():
            set_frozen(True)
            db.session.add(Solve(user_id=2, team_id=1, challenge_id=1, points_earned=100, is_first_blood=True))
            db.session.commit()
            cache_service.invalidate_scoreboard()
            WebSocketService.emit_scoreboard_update([{'score': 100}])
            WebSocketService.emit_new_solve({'score': 100})
        self.assertFalse(live.get_received('/live'))
        for path in ['/scoreboard/api/data', '/scoreboard/api/top/3', '/scoreboard/api/data?nearby=1']:
            self.assertEqual(self.client.get(path).json[0]['score'], 0)
        from unittest.mock import patch
        from flask_login import login_user
        from models.user import User
        from services.websocket import handle_request_scoreboard
        with app.test_request_context(), patch('services.websocket.emit') as emit:
            login_user(db.session.get(User, 2))
            handle_request_scoreboard()
            self.assertEqual(emit.call_args.args[1][0]['score'], 0)
        self.client.get('/logout')
        self.login(admin=True)
        row = self.client.get('/scoreboard/api/data').json[0]
        self.assertEqual((row['score'], row['first_bloods']), (100, 1))
        with app.app_context():
            set_frozen(False)
        self.client.get('/logout')
        self.login()
        self.assertEqual(self.client.get('/scoreboard/api/data').json[0]['score'], 100)
        live.disconnect(namespace='/live')

    def test_nearby_beyond_top_100_and_solo_mode(self):
        with app.app_context():
            for i in range(105):
                team = Team(name=f'Ranked {i}', invite_code=f'TEST{i}', captain_id=1)
                db.session.add(team)
                db.session.flush()
                db.session.add(Solve(user_id=1, team_id=team.id, points_earned=10))
            db.session.commit()
        self.login()
        self.assertEqual(len(self.client.get('/scoreboard/api/data').json), 100)
        nearby = self.client.get('/scoreboard/api/data?nearby=1').json
        self.assertEqual(nearby[-1]['id'], 1)
        self.assertEqual(nearby[-1]['rank'], 106)
        with app.app_context():
            Settings.set('teams_enabled', False, 'bool')
        self.assertTrue(any(row['id'] == 2 for row in self.client.get('/scoreboard/api/data?nearby=1').json))

    def test_status_and_hidden_scoreboard(self):
        self.assertEqual(self.client.get('/api/competition-status').status_code, 302)
        self.login()
        with app.app_context():
            Settings.set('ctf_end_time', datetime.utcnow() + timedelta(hours=1), 'datetime')
            Settings.set('ctf_paused', True, 'bool')
            set_frozen(True)
            Settings.set('scoreboard_visible', False, 'bool')
        status = self.client.get('/api/competition-status').json
        self.assertEqual(status['status'], 'paused')
        self.assertTrue(status['frozen_at'])
        self.assertTrue(status['end'].endswith('+00:00'))
        self.assertEqual(self.client.get('/scoreboard/api/data?nearby=1').json, [])


if __name__ == '__main__':
    unittest.main()
