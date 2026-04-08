.PHONY: app venv setup

app:
	HOST=0.0.0.0 .venv/bin/python app.py

venv: 
	source .venv/bin/activate

setup:
	python3 -m venv .venv
	source .venv/bin/activate
	pip install -r requirements.txt