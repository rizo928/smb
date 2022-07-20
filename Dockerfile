FROM python:3.9-buster
WORKDIR /app

COPY ./requirements.txt /app
RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir /app/templates; \
    mkdir /app/static; \
    rm /app/requirements.txt

COPY ./* /app
COPY ./static/* /app/static
COPY ./templates/* /app/templates

EXPOSE 5000/tcp

CMD ["uwsgi","--http", "0.0.0.0:5000", "--wsgi-file", "wsgi.py", "--callable", "app", "--master", "--processes", "4", "--threads", "2"]