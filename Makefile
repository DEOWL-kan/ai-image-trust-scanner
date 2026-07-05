.PHONY: install install-models run run-models test doctor

install:
	python -m pip install --upgrade pip
	pip install -r requirements.txt

install-models:
	pip install -r requirements-open-source.txt

run:
	python scripts/run_local_dashboard.py

run-models:
	python scripts/run_local_dashboard.py --with-models

test:
	pytest tests -q -m "not hf and not torch and not local_data and not legacy"

doctor:
	python scripts/doctor.py
