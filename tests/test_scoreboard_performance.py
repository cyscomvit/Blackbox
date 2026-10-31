"""Score parity and bounded-query regression for uncached event standings."""
import unittest
from time import perf_counter
from sqlalchemy import event
from tests.ui_fixture import seed, app
from models import db
from models.team import Team
from models.user import User
from models.challenge import Challenge
from models.submission import Solve
from models.hint import HintUnlock, Hint
from models.settings import Settings
from services.scoring import ScoringService


class ScoreboardPerformance(unittest.TestCase):
    def test_bulk_scores_match_existing_rules_and_bound_queries(self):
        seed()
        with app.app_context():
            challenge = db.session.get(Challenge, 1)
            challenge.is_dynamic = True
            challenge.decay_solves = 1000
            Settings.set('first_blood_bonus', 25, 'int')
            solo = User(username='solo', email='solo@example.test', password_hash='unused-test-hash', is_active=True)
            db.session.add(solo)
            db.session.flush()
            db.session.add(Solve(user_id=solo.id, challenge_id=1, points_earned=100))
            db.session.add(Solve(user_id=solo.id, points_earned=-17))
            db.session.add(HintUnlock(hint_id=1, user_id=solo.id, cost_paid=9))
            for i in range(250):
                team = Team(name=f'Benchmark {i}', invite_code=f'B{i:07}', is_active=i != 249)
                db.session.add(team)
                db.session.flush()
                db.session.add(Solve(team_id=team.id, challenge_id=1, points_earned=100, is_first_blood=i == 0))
                db.session.add(Solve(team_id=team.id, points_earned=i % 13 - 6))
                db.session.add(HintUnlock(hint_id=1, user_id=solo.id, team_id=team.id, cost_paid=i % 7))
            db.session.commit()
            for decay in ['logarithmic', 'parabolic']:
                Settings.set('decay_function', decay)
                for team_based in [True, False]:
                    statements = []
                    def record(*args): statements.append(args[2])
                    event.listen(db.engine, 'before_cursor_execute', record)
                    try:
                        start = perf_counter()
                        rows = ScoringService.get_scoreboard(team_based=team_based)
                        elapsed = perf_counter() - start
                    finally:
                        event.remove(db.engine, 'before_cursor_execute', record)
                    self.assertLessEqual(len(statements), 8)
                    print(f'{decay} team={team_based}: {len(rows)} entries, {len(statements)} SQL queries, {elapsed:.3f}s')
                    entrants = Team.query.filter_by(is_active=True).all() if team_based else User.query.filter_by(is_active=True).all()
                    expected = {}
                    old_start = perf_counter()
                    old_queries = []
                    def old_record(*args): old_queries.append(args[2])
                    event.listen(db.engine, 'before_cursor_execute', old_record)
                    try:
                        for entrant in entrants:
                            last = entrant.solves.order_by(Solve.solved_at.desc()).first()
                            expected[entrant.id] = (entrant.get_score(), entrant.get_solves_count(), last.solved_at.isoformat() if last else None)
                    finally:
                        event.remove(db.engine, 'before_cursor_execute', old_record)
                    print(f'Previous calculation: {len(old_queries)} SQL queries, {perf_counter()-old_start:.3f}s')
                    self.assertEqual({r['id']:(r['score'],r['solves'],r['last_solve']) for r in rows}, expected)
                    self.assertEqual([r['rank'] for r in rows], list(range(1,len(rows)+1)))
