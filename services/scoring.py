import math
from models.challenge import Challenge
from models.submission import Solve
from models.team import Team
from models.user import User

class ScoringService:
    """Service for managing challenge scoring and calculations"""
    
    @staticmethod
    def calculate_dynamic_points(challenge, solve_count=None, decay_function=None):
        """
        Calculate dynamic points for a challenge based on solve count
        Supports both logarithmic and parabolic decay functions
        """
        if not challenge.is_dynamic:
            return challenge.initial_points
        
        if solve_count is None:
            solve_count = challenge.get_solves_count()
        
        if solve_count <= 1:
            return challenge.initial_points
            
        # Shift so decay begins AFTER the first solve
        solve_count -= 1
        
        # If we've reached the decay threshold, return minimum
        if solve_count >= challenge.decay_solves:
            return challenge.minimum_points
        
        # Get decay function from Settings or config
        from flask import current_app
        from models.settings import Settings
        
        if decay_function is None:
            decay_function = Settings.get('decay_function', 'string')
        if not decay_function:
            decay_function = current_app.config.get('DECAY_FUNCTION', 'logarithmic')
        
        max_points = challenge.initial_points
        min_points = challenge.minimum_points
        decay = challenge.decay_solves
        
        if decay_function == 'parabolic':
            # Parabolic decay (CTFd-style)
            # Formula: value = (((minimum - initial) / (decay²)) * (solves²)) + initial
            # Steeper decrease early on, then levels out
            points = (((min_points - max_points) / (decay ** 2)) * (solve_count ** 2)) + max_points
            points = math.ceil(points)
        else:
            # Logarithmic decay (default)
            # Smooth, gradual decrease using natural log
            points = max_points - (max_points - min_points) * \
                     (math.log(solve_count + 1) / math.log(decay + 1))
            points = int(points)
        
        return max(points, min_points)
    
    @staticmethod
    def get_scoreboard(team_based=True, limit=None):
        """
        Get scoreboard with rankings
        
        Args:
            team_based: If True, return team scores. If False, return individual scores
            limit: Maximum number of entries to return
        
        Returns:
            List of dictionaries with score information
        """
        from collections import defaultdict
        from models import db
        from models.hint import HintUnlock
        from models.settings import Settings

        # Read scalar rows in bulk: no lazy relationships or per-entrant queries.
        challenges = {c.id: c for c in Challenge.query.all()}
        solves = db.session.query(Solve.user_id, Solve.team_id, Solve.challenge_id,
                                  Solve.points_earned, Solve.is_first_blood, Solve.solved_at).all()
        counts = defaultdict(int)
        for solve in solves:
            if solve.challenge_id is not None:
                counts[solve.challenge_id] += 1
        decay = Settings.get('decay_function', 'string')
        bonus = Settings.get('first_blood_bonus', 0, type='int')
        values = {cid: ScoringService.calculate_dynamic_points(c, counts[cid], decay)
                  for cid, c in challenges.items() if c.is_dynamic}
        team_scores, user_scores = defaultdict(int), defaultdict(int)
        team_counts, user_counts = defaultdict(int), defaultdict(int)
        team_last, user_last = {}, {}
        team_first, user_first = defaultdict(int), defaultdict(int)
        for solve in solves:
            if solve.challenge_id is not None and solve.is_first_blood:
                team_first[solve.team_id] += 1
                user_first[solve.user_id] += 1
            points = values.get(solve.challenge_id, solve.points_earned)
            if solve.challenge_id in values and solve.is_first_blood:
                points += bonus
            for owner, scores, totals, latest in (
                (solve.team_id, team_scores, team_counts, team_last),
                (solve.user_id, user_scores, user_counts, user_last),
            ):
                if owner is None:
                    continue
                scores[owner] += points
                totals[owner] += int(solve.challenge_id is not None)
                if solve.solved_at and (owner not in latest or solve.solved_at > latest[owner]):
                    latest[owner] = solve.solved_at
        # Keep team hint charges separate from individual hint charges.
        for user_id, team_id, cost in db.session.query(
                HintUnlock.user_id, HintUnlock.team_id, db.func.sum(HintUnlock.cost_paid)
        ).group_by(HintUnlock.user_id, HintUnlock.team_id):
            if team_id is not None:
                team_scores[team_id] -= int(cost)
            else:
                user_scores[user_id] -= int(cost)
        scoreboard = []
        if team_based:
            entrants = db.session.query(Team.id, Team.name, Team.affiliation).filter(Team.is_active.is_(True)).all()
            for entrant in entrants:
                last = team_last.get(entrant.id)
                scoreboard.append(dict(id=entrant.id, name=entrant.name, affiliation=entrant.affiliation,
                                       score=team_scores[entrant.id], solves=team_counts[entrant.id],
                                       last_solve=last.isoformat() if last else None))
        else:
            # Preserve existing behaviour: team members inherit their team's score,
            # but their solve count and tie-break timestamp remain individual.
            team_ids = {row.id for row in db.session.query(Team.id)}
            entrants = db.session.query(User.id, User.username, User.full_name, User.team_id).filter(User.is_active.is_(True)).all()
            for entrant in entrants:
                last = user_last.get(entrant.id)
                score = (team_scores[entrant.team_id] if entrant.team_id in team_ids else 0) if entrant.team_id else user_scores[entrant.id]
                scoreboard.append(dict(id=entrant.id, name=entrant.username, affiliation=entrant.full_name or '',
                                       score=score, solves=user_counts[entrant.id],
                                       last_solve=last.isoformat() if last else None))
        scoreboard.sort(key=lambda entry: (-entry['score'], entry['last_solve'] or '9999', entry['id']))

        # Add rankings
        for rank, entry in enumerate(scoreboard, 1):
            entry['rank'] = rank
            entry['first_bloods'] = (team_first if team_based else user_first)[entry['id']]
        
        # Apply limit if specified
        if limit:
            scoreboard = scoreboard[:limit]
        
        return scoreboard
    
    @staticmethod
    def get_challenge_statistics():
        """Get statistics for all challenges"""
        challenges = Challenge.query.filter_by(is_visible=True, is_enabled=True).all()
        
        stats = []
        for challenge in challenges:
            solves = challenge.get_solves_count()
            submissions = challenge.get_submissions_count()
            
            stats.append({
                'id': challenge.id,
                'name': challenge.name,
                'category': challenge.category,
                'points': challenge.get_current_points(),
                'solves': solves,
                'submissions': submissions,
                'solve_rate': (solves / submissions * 100) if submissions > 0 else 0
            })
        
        return stats
    
    @staticmethod
    def get_user_progress(user_id):
        """Get detailed progress for a user"""
        user = User.query.get(user_id)
        if not user:
            return None
        
        solves = Solve.query.filter_by(user_id=user_id).all()
        
        progress = {
            'total_score': user.get_score(),
            'challenges_solved': len(solves),
            'solves': []
        }
        
        for solve in solves:
            # Skip if challenge has been deleted
            if not solve.challenge:
                continue
                
            progress['solves'].append({
                'challenge_id': solve.challenge_id,
                'challenge_name': solve.challenge.name,
                'category': solve.challenge.category,
                'docker_enabled': solve.challenge.docker_enabled,
                'points_earned': solve.points_earned,
                'solved_at': solve.solved_at.isoformat()
            })
        
        return progress
    
    @staticmethod
    def get_team_progress(team_id):
        """Get detailed progress for a team"""
        team = Team.query.get(team_id)
        if not team:
            return None
        
        solves = Solve.query.filter_by(team_id=team_id).all()
        
        progress = {
            'total_score': team.get_score(),
            'challenges_solved': len(solves),
            'solves': []
        }
        
        for solve in solves:
            # Skip if challenge has been deleted
            if not solve.challenge:
                continue
                
            solver = User.query.get(solve.user_id)
            progress['solves'].append({
                'challenge_id': solve.challenge_id,
                'challenge_name': solve.challenge.name,
                'category': solve.challenge.category,
                'points_earned': solve.points_earned,
                'solved_at': solve.solved_at.isoformat(),
                'solved_by': solver.username if solver else 'Unknown'
            })
        
        return progress
