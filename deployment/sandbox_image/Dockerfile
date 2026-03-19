FROM python:3.11-slim

RUN useradd -m -s /bin/bash sandbox

RUN pip install --no-cache-dir \
    numpy pandas scipy matplotlib seaborn \
    scikit-learn statsmodels networkx sympy

RUN mkdir /workspace /output && \
    chown sandbox:sandbox /workspace /output

USER sandbox
WORKDIR /workspace
