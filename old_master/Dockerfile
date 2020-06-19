FROM python:3

WORKDIR /var/worker

RUN apt-get update
RUN apt-get install -y openssh-server sudo vim git curl

COPY /certificates/dev-certificate.pub /authorized_keys
RUN mkdir -p ~root/.ssh /var/run/sshd \
    && chmod 700 ~root/.ssh \
    && mv /authorized_keys ~root/.ssh/authorized_keys \
    && chmod 600 ~root/.ssh/authorized_keys

COPY / /var/master/
WORKDIR /var/master
RUN pip install --no-cache-dir -r /var/master/requirements.txt

EXPOSE 8000 22
CMD ["/usr/sbin/sshd", "-D"]