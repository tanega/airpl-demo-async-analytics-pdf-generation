FROM python:3.11-slim

WORKDIR /code

RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    mkdir -p /opt/quarto && \
    curl -sL "https://github.com/quarto-dev/quarto-cli/releases/download/v1.9.38/quarto-1.9.38-linux-amd64.tar.gz" \
    | tar -xz --strip-components=1 -C /opt/quarto && \
    ln -s /opt/quarto/bin/quarto /usr/local/bin/quarto && \
    apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

ENV QUARTO_PYTHON=/usr/local/bin/python3
ENV MPLBACKEND=Agg

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY reports ./reports

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
