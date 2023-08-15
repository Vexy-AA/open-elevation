FROM osgeo/gdal:ubuntu-small-latest-amd64

RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y libspatialindex-dev unar bc python3-pip wget libgdal-dev gdal-bin

ADD ./requirements.txt .
RUN pip install -r requirements.txt

RUN mkdir /code
ADD . /code/

WORKDIR /code
RUN chmod a+x start.sh
CMD ["./start.sh"]
#CMD python3 /code/data/config/server.py

EXPOSE 8080
EXPOSE 8000
EXPOSE 8443
