FROM mcr.microsoft.com/devcontainers/python:1-3.12-bullseye

WORKDIR /workspace

COPY requirements.txt /workspace

RUN pip3 install -r requirements.txt

COPY src /workspace/src
