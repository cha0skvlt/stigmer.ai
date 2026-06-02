FROM python:3.13-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
    && sed -i 's|backend/alembic|alembic|' alembic.ini

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
