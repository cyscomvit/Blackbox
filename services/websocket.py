from flask_socketio import SocketIO, emit, join_room, leave_room, rooms
from flask import request
from flask_login import current_user

# Since gunicorn.conf.py already runs worker_class = 'gevent' and app.py already monkey-patches for gevent, just make Socket.IO consistent with that instead of eventlet.
socketio = SocketIO(cors_allowed_origins="*", async_mode='gevent')

class WebSocketService:
    """Service for managing WebSocket connections and real-time updates"""
    
    @staticmethod
    def init_app(app):
        """Initialize SocketIO with Flask app"""
        socketio.init_app(app, cors_allowed_origins="*", async_mode='gevent',
                         logger=app.debug, engineio_logger=app.debug)
    
    @staticmethod
    def emit_scoreboard_update(scoreboard_data):
        """Emit scoreboard update to all connected clients"""
        from models.settings import Settings
        from services.standings import frozen_snapshot
        public = not frozen_snapshot() and Settings.is_ctf_started() and Settings.get('scoreboard_visible', default=True, type='bool')
        socketio.emit('scoreboard_update', scoreboard_data, namespace='/live', to='scoreboard_authenticated' if public else 'scoreboard_admin')
    
    @staticmethod
    def emit_new_solve(solve_data):
        """Emit new solve notification"""
        from models.settings import Settings
        from services.standings import frozen_snapshot
        visible = not frozen_snapshot() and Settings.is_ctf_started() and Settings.get('scoreboard_visible', default=True, type='bool')
        socketio.emit('new_solve', solve_data, namespace='/live', to='scoreboard_authenticated' if visible else 'scoreboard_admin')
    
    @staticmethod
    def emit_challenge_update(challenge_data):
        """Emit challenge update (points change)"""
        socketio.emit('challenge_update', challenge_data, namespace='/live')

    @staticmethod
    def emit_notification(notification_data):
        """Emit a generic notification to all connected clients"""
        socketio.emit('notification', notification_data, namespace='/live')

    @staticmethod
    def emit_notification_deleted(notification_id):
        """Notify clients that a notification was deleted"""
        socketio.emit('notification_deleted', {'id': notification_id}, namespace='/live')


# WebSocket event handlers
@socketio.on('connect', namespace='/live')
def handle_connect():
    """Handle client connection"""
    if current_user.is_authenticated:
        join_room('scoreboard_authenticated')
        if current_user.is_admin:
            join_room('scoreboard_admin')
    print(f'Client connected: {request.sid}')
    emit('connected', {'data': 'Connected to live updates'})


@socketio.on('disconnect', namespace='/live')
def handle_disconnect():
    """Handle client disconnection"""
    print(f'Client disconnected: {request.sid}')


@socketio.on('join_scoreboard', namespace='/live')
def handle_join_scoreboard():
    """Client joins scoreboard room for live updates"""
    if not current_user.is_authenticated:
        return
    join_room('scoreboard')
    emit('status', {'msg': 'Joined scoreboard room'})


@socketio.on('leave_scoreboard', namespace='/live')
def handle_leave_scoreboard():
    """Client leaves scoreboard room"""
    leave_room('scoreboard')
    emit('status', {'msg': 'Left scoreboard room'})


@socketio.on('request_scoreboard', namespace='/live')
def handle_request_scoreboard():
    """Client requests current scoreboard data"""
    from services.scoring import ScoringService
    from services.cache import cache_service
    from models.settings import Settings
    
    is_admin = current_user.is_authenticated and current_user.is_admin
    if not current_user.is_authenticated or (not is_admin and (not Settings.is_ctf_started() or not Settings.get('scoreboard_visible', default=True, type='bool'))):
        emit('scoreboard_update', [])
        return

    from services.standings import standings_for
    scoreboard = standings_for(current_user)[:100]

    emit('scoreboard_update', scoreboard)


@socketio.on('ping', namespace='/live')
def handle_ping():
    """Handle ping from client"""
    emit('pong', {'timestamp': str(__import__('datetime').datetime.utcnow())})
