# Brack Idea Ring

This project now includes a Flask game server with three screens:

- Master screen: manage teams, leaders, ideas, brackets, and stage controls.
- Game screen: public progress view with a QR code and login URL.
- User screen: persistent login page and player dashboard.

Run it
------

1. Install dependencies: `pip install -r requirements.txt`
2. Start the server: `python app.py`
3. Open:
	- Master: `/master`
	- Game: `/game`
	- User login: `/user` or scan the QR code from the game screen

Game state is saved to `data/game_state.json`.
