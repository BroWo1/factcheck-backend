#!/bin/sh

# Start Redis
redis-server --daemonize yes

# Start Celery worker
celery -A factcheck_backend worker --loglevel=info --pool=solo &

# Start Daphne ASGI server
daphne -b 0.0.0.0 -p 8000 factcheck_backend.asgi:application
