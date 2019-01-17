FROM balenalib/rpi-alpine
RUN [ "cross-build-start" ]
RUN apk add --no-cache python3
RUN apk add --no-cache --virtual build \
        git && \
    git clone https://github.com/LelandSindt/teslajson.git && \
    cd /teslajson && \
    python3 setup.py install && \
    cd / && \
    rm -rf /teslajson  &&\
    apk del build
RUN pip3 --disable-pip-version-check --no-cache-dir install geopy requests
RUN [ "cross-build-end" ]
ADD query.py ./query.py
CMD ["python3","-u","./query.py"]
