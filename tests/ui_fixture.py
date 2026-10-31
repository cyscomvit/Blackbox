"""Isolated UI data. Never connects to the configured production database."""
import os
os.environ['FLASK_ENV'] = 'testing'

from app import app
from models import db
from models.user import User
from models.team import Team
from models.challenge import Challenge
from models.hint import Hint
from models.settings import Settings
from services.cache import cache, cache_service
from fakeredis import FakeRedis


# Some admin-only models are imported lazily by routes.
import importlib
import pkgutil
import models
for module in pkgutil.iter_modules(models.__path__):
    importlib.import_module(f'models.{module.name}')


def seed():
    with app.app_context():
        db.drop_all()
        db.create_all()
        cache.clear()
        cache_service.redis_client = FakeRedis(decode_responses=True)
        admin = User(username='preview-admin', email='admin@example.test', is_admin=True, is_verified=True)
        admin.set_password('PreviewOnly123!')
        player = User(username='preview-player', email='player@example.test', is_verified=True)
        player.set_password('PreviewOnly123!')
        db.session.add_all([admin, player])
        db.session.flush()
        team = Team(name='Packet Inspectors', invite_code='PREVIEW1', captain_id=player.id, affiliation='CYSCOM')
        db.session.add(team)
        db.session.flush()
        player.team_id = team.id
        player.is_team_captain = True
        challenge = Challenge(name='Inspect the request', description='Find the flag in the supplied HTTP response. Preview flag: CYSCOM{local_preview}', category='Web', act='ACT I', flag='CYSCOM{local_preview}', initial_points=100, minimum_points=50, is_dynamic=False, difficulty='easy')
        db.session.add(challenge)
        db.session.flush()
        db.session.add(Hint(challenge_id=challenge.id, content='Inspect the response headers.', cost=0, order=0))
        db.session.commit()
        Settings.set('ctf_name', 'CYSCOM')
        Settings.set('ctf_description', 'Capture the flag. Solve challenges, compare techniques, and follow the standings.')
        Settings.set('teams_enabled', True, 'bool')
        Settings.set('scoreboard_visible', True, 'bool')
        Settings.set('act_system_enabled', False, 'bool')
    return app
