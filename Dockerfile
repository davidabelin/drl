FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYGAME_HIDE_SUPPORT_PROMPT=1 \
    SDL_VIDEODRIVER=dummy \
    SDL_AUDIODRIVER=dummy \
    XDG_RUNTIME_DIR=/tmp \
    DRL_LUNAR_JOBS_ROOT=/tmp/drl_lunar_jobs

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential swig \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["sh", "-c", "gunicorn --worker-tmp-dir /tmp --bind :${PORT:-8080} run:app"]
