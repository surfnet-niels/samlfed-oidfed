FROM ubuntu
RUN apt update 
RUN apt install -y locales python3-jwcrypto python3-git python3-yaml 
RUN rm -rf /var/lib/apt/lists/* \
    && localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8
ENV LANG=en_US.utf8
