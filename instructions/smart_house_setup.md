Smart-house Pi3 (Ubuntu): auth_log_monitor.service
1) Create directories + copy script
sudo mkdir -p /opt/labtools/smart_house /var/log/labtools
sudo cp auth_log_monitor.py /opt/labtools/smart_house/
sudo chmod +x /opt/labtools/smart_house/auth_log_monitor.py

2) Unit file: /etc/systemd/system/auth_log_monitor.service
[Unit]
Description=LabTools - Auth Log Monitor (smart house)
After=network.target
Wants=network.target

[Service]
Type=simple
# Needs root to read /var/log/auth.log reliably
User=root
Group=root
ExecStart=/usr/bin/python3 /opt/labtools/smart_house/auth_log_monitor.py --authlog /var/log/auth.log --out /var/log/labtools/iot_auth_events.jsonl
Restart=always
RestartSec=2
# Hardening (safe for log tailers)
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=/var/log/labtools
# auth.log is under /var/log; allow read
ReadOnlyPaths=/var/log/auth.log

[Install]
WantedBy=multi-user.target

3) Enable + start
sudo systemctl daemon-reload
sudo systemctl enable --now auth_log_monitor.service
sudo systemctl status auth_log_monitor.service --no-pager