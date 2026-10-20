FROM nodered/node-red:4.0.9
USER root
RUN npm --prefix /data install --save-exact --omit=dev --no-audit --no-fund node-red-contrib-postgresql@0.16.2 \
    && chown -R node-red:node-red /data
USER node-red
