FROM python:3.12-slim
WORKDIR /app
COPY app.py policies.json ./
USER nobody
EXPOSE 8080
ENV POLICIES_PATH=/app/policies.json
CMD ["python", "/app/app.py"]
