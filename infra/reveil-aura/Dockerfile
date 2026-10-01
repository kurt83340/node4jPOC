# Job Cloud Run reveil-aura (NEO-13) : bibliothèque standard seule, rien à installer.
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY reveil.py .

# Pas besoin de root : le script lit un fichier monté et ouvre une connexion HTTPS.
USER nobody
ENTRYPOINT ["python", "reveil.py"]
