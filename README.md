RPiMusic
===

Get AMQP message, play URL (via mpv, currently).
This script creates an exchange and a queue in the specified AMQP vhost.
Only ssl-enabled AMQP connections are supported.
The exchange is named "Xall", type direct.
The queue is named "RPiMusic_uuid", with uuid being the uuid from the config file.

Example rpimusic.conf
```json
{ 
  "amqp_url": "amqp://user:password@amqp.example.com/examplevhost",
  "fallback_playlist_url": "http://radio.example.com/playlist.m3u",
  "url_cache_file": "/var/lib/rpimusic/playlistcache.json",
  "uuid": "c788176f2e4747f3ae2fe15083d97dce"
}
```

Example systemd unit file
```
[Unit]
Description=Listens for AMQP messages containing URLs and plays them via mpv
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=rpimusic
ExecStart=/opt/venv/bin/rpimusicd --config /etc/rpimusic.conf
Restart=on-failure
RestartSec=30
RestartPreventExitStatus=255

[Install]
WantedBy=multi-user.target
```
