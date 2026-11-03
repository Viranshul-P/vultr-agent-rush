FROM mitmproxy/mitmproxy:11.0.2
COPY airlock_addon.py /opt/airlock_addon.py
ENV PROXY_LOG_DIR=/logs
EXPOSE 8080
CMD ["mitmdump", "-s", "/opt/airlock_addon.py", "--listen-port", "8080", "--set", "block_global=false", "--set", "connection_strategy=lazy"]
