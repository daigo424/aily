FROM arigaio/atlas:latest-alpine

WORKDIR /work

ENTRYPOINT ["atlas"]
CMD ["version"]