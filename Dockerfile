#
# Spiderfoot Dockerfile
#
# http://www.spiderfoot.net
#
# Written by: Michael Pellon <m@pellon.io>
# Updated by: Chandrapal <bnchandrapal@protonmail.com>
# Updated by: Steve Micallef <steve@binarypool.com>
# Updated by: Steve Bate <svc-spiderfoot@stevebate.net>
#    -> Inspired by https://github.com/combro2k/dockerfiles/tree/master/alpine-spiderfoot
#
# Usage:
#
#   sudo docker build -t spiderfoot .
#   sudo docker run -p 5001:5001 spiderfoot
#
# Using Docker volume for spiderfoot data
#
#   sudo docker run -p 5001:5001 -v /mydir/spiderfoot:/var/lib/spiderfoot spiderfoot
#
# Using SpiderFoot remote command line with web server
#
#   docker run --rm -it spiderfoot sfcli.py -s http://my.spiderfoot.host:5001/
#
# Running spiderfoot commands without web server (can optionally specify volume)
#
#   sudo docker run --rm spiderfoot sf.py -h
#
# Running spiderfoot unit tests in container
#   sudo docker build -t spiderfoot-test --build-arg REQUIREMENTS=requirements_test.txt .
#   sudo docker run --rm spiderfoot-test -m pytest --flake8 .

FROM alpine:3.9.6
ARG REQUIREMENTS=requirements.txt
RUN apk add --no-cache gcc git curl python3 python3-dev py3-pip swig tinyxml-dev \
 python3-dev musl-dev openssl-dev libffi-dev libxslt-dev libxml2-dev jpeg-dev \
 openjpeg-dev zlib-dev
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin":$PATH
COPY $REQUIREMENTS requirements.txt ./
RUN ls
RUN echo "$REQUIREMENTS"
RUN pip3 install -r "$REQUIREMENTS"



FROM alpine:3.9.6
WORKDIR /home/spiderfoot
# Place database and configs outside installation directory
ENV SPIDERFOOT_DATA /var/lib/spiderfoot

# Run everything as one command so that only one layer is created
RUN apk --update --no-cache add python3 musl openssl libxslt tinyxml libxml2 jpeg zlib openjpeg \
    && addgroup spiderfoot \
    && adduser -G spiderfoot -h /home/spiderfoot -s /sbin/nologin \
               -g "SpiderFoot User" -D spiderfoot \
    && rm -rf /var/cache/apk/* \
    && rm -rf /lib/apk/db \
    && rm -rf /root/.cache \
    && mkdir $SPIDERFOOT_DATA \
    && chown spiderfoot:spiderfoot $SPIDERFOOT_DATA

COPY . .

# fix permissions on logs directory
ENV SPIDERFOOT_LOGS /home/spiderfoot/log
RUN chown spiderfoot:spiderfoot $SPIDERFOOT_LOGS

COPY --from=build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

USER spiderfoot

EXPOSE 5001

# Run the application.
ENTRYPOINT ["/opt/venv/bin/python"]
CMD ["sf.py", "-l", "0.0.0.0:5001"]
