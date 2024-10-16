FROM mcr.microsoft.com/playwright:v1.46.0-noble

RUN apt update
RUN apt -y install nginx python3 python3-pip fonts-noto-core

COPY default.png /var/www/html/screenshot.png

COPY requirements.txt /
RUN pip install -r /requirements.txt --break-system-packages

RUN playwright install webkit --with-deps

COPY . .
ENTRYPOINT service nginx restart && exec python3 main.py
