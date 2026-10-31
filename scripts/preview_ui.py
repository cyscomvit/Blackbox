"""Run a disposable local UI preview, with no MySQL, Redis or Docker required."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.ui_fixture import seed
from services.websocket import socketio

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=5050)
    port = parser.parse_args().port
    app = seed()
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.jinja_env.auto_reload = True
    print(f'Local UI preview: http://127.0.0.1:{port}', flush=True)
    print('Accounts: preview-admin / preview-player; password: PreviewOnly123!', flush=True)
    print('Disposable in-memory data. Restart to reset. Docker and email are not configured.', flush=True)
    socketio.run(app, host='127.0.0.1', port=port, debug=False, use_reloader=False, log_output=False)
