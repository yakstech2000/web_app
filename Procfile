web: gunicorn web_app.wsgi --log-file -
release: python manage.py collectstatic --noinput && python manage.py migrate