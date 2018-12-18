FROM alpine 
RUN apk add --no-cache python3
RUN apk add --no-cache --virtual build \
        git && \
    git clone https://github.com/LelandSindt/teslajson.git && \
    cd /teslajson && \
    python3 setup.py install && \
    cd / && \
    rm -rf /teslajson  &&\
    apk del build
RUN pip3 --disable-pip-version-check --no-cache-dir install geopy 
ADD query.py ./query.py
CMD ["python3","-u","./query.py"]
