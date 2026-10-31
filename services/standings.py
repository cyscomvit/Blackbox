"""One access policy for HTTP and socket standings, including durable freezes."""
import json
from datetime import datetime
from models.settings import Settings
from services.scoring import ScoringService


def frozen_snapshot():
    raw = Settings.get('scoreboard_snapshot')
    return json.loads(raw) if raw else None


def set_frozen(enabled):
    if enabled and not frozen_snapshot():
        snapshot = {
            'at': datetime.utcnow().isoformat() + 'Z',
            'teams': ScoringService.get_scoreboard(team_based=True),
            'individuals': ScoringService.get_scoreboard(team_based=False),
        }
        Settings.set('scoreboard_snapshot', json.dumps(snapshot))
    elif not enabled:
        Settings.set('scoreboard_snapshot', None)


def standings_for(user):
    if not user.is_authenticated:
        return []
    if not user.is_admin and (not Settings.is_ctf_started() or not Settings.get('scoreboard_visible', True, type='bool')):
        return []
    teams = Settings.get('teams_enabled', True, type='bool')
    snapshot = frozen_snapshot()
    if snapshot and not user.is_admin:
        return snapshot['teams' if teams else 'individuals']
    from services.cache import cache_service
    key = 'scoreboard_full_team' if teams else 'scoreboard_full_individual'
    rows = cache_service.get(key)
    if rows is None:
        rows = ScoringService.get_scoreboard(team_based=teams)
        cache_service.set(key, rows, ttl=60)
    return rows
