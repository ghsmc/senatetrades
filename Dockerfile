FROM python:3.9

ENV PYTHONUNBUFFERED True

WORKDIR /app
RUN pip install poetry
COPY pyproject.toml poetry.lock /app/

RUN poetry config virtualenvs.create false \
  && poetry install --no-dev --no-interaction --no-ansi

COPY congressmoney/ congressmoney/

# COPY processed_senators.json /app/processed_senators.json
COPY congressmoney /processed_senators.json

CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 0 congressmoney.app:app