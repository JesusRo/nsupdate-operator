FROM python:3.13.5-alpine AS base
RUN mkdir /app
WORKDIR /app
COPY requirements.txt /requirements.txt
RUN pip install -r /requirements.txt
COPY app /app
CMD ["kopf", "run", "--liveness=http://0.0.0.0:8080/", "-A", "controller.py"]