# Brack Idea Ring

This project now includes a Flask game server with three screens:

- Master screen: manage teams, leaders, ideas, brackets, and stage controls.
- Game screen: public progress view with a QR code and login URL.
- User screen: persistent login page and player dashboard.

Run it
------

1. Install dependencies: `.venv/bin/pip install -r requirements.txt`
2. Start the server:
   - **Locally only** (default): `.venv/bin/python app.py`
   - **Internet accessible**: `HOST=0.0.0.0 .venv/bin/python app.py`

3. Open:
   - Master (localhost only): `http://127.0.0.1:5000/master`
   - Game (localhost only): `http://127.0.0.1:5000/game`
   - User login: `http://127.0.0.1:5000/user` or from internet when HOST=0.0.0.0

Game state is saved to `data/game_state.json`.

### For internet play:

When running with `HOST=0.0.0.0`, players can join from any device on your network or the internet. Share the login URL from the game screen (usually your computer's IP address and port 5000, e.g., `http://192.168.1.100:5000/user`).
