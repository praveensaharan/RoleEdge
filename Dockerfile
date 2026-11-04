# RoleEdge on Cloud Run. Build: docker build -t roleedge .   Run: docker run -p 8080:8080 -e META_API_KEY=... roleedge
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ffmpeg: reels, link downloads and voice notes
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home app
WORKDIR /app

# Dependencies first, so a code-only change reuses this layer. The editable install puts /app/src on the path,
# which the app needs: config.py finds web/, data/ and output/ relative to the repository root (/app).
COPY pyproject.toml ./
RUN mkdir -p src/roleedge && touch src/roleedge/__init__.py && pip install -e .

COPY . .
RUN mkdir -p output && chown -R app:app /app
USER app

# Cloud Run sets PORT (8080 by default)
EXPOSE 8080
CMD exec roleedge serve --host 0.0.0.0 --port ${PORT:-8080}
