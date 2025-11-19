python manage.py migrate --noinput
python manage.py collectstatic --noinput
gunicorn goProjet.wsgi:application