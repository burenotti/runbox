FROM gcc:10

RUN useradd -M -d /sandbox sandbox && \
    mkdir /sandbox && \
    chown -R sandbox:sandbox /sandbox

WORKDIR /sandbox

CMD ["g++", "main.cpp", "-o", "./main"]