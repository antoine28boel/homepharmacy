FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /opt/pharmacie
COPY app ./app
EXPOSE 8099
CMD ["python", "-m", "app"]
