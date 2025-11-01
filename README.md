Event Finder is a webapp which integrates messaging into the event discovery and creation theme.

### Create & activate virtual env
python -m venv .venv
.venv\Scripts\activate # Windows
# or
source .venv/bin/activate # macOS/Linux/Codespaces

### Install dependencies
pip install -r requirements.txt
# (If you do not have one yet, run:)
pip install django channels daphne channels-redis
pip freeze > requirements.txt

### Database migrations & admin
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser # create an admin for testing

### (If using Redis locally) start and verify
redis-server --daemonize yes # in Codespaces/Linux/macOS
redis-cli ping # expect: PONG

### Run the dev server
python manage.py runserver 0.0.0.0:8000
# Visit http://127.0.0.1:8000 (or forwarded Codespaces port)

