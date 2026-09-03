#!/bin/bash
set -e   # останавливаем скрипт при первой же ошибке, чтобы не продолжать вслепую

# ==== настройки ====
REPO_URL="https://github.com/nadushaem/data_science_jobs_radar.git"
BOT_USER="botuser"
SERVICE_NAME="data-science-jobs-radar"
# имя папки проекта берем из url репозитория автоматически (без .git на конце)
PROJECT_DIR=$(basename "$REPO_URL" .git)
HOME_DIR="/home/$BOT_USER"
PROJECT_PATH="$HOME_DIR/$PROJECT_DIR"

echo "=== шаг 1: обновляем систему и ставим пакеты ==="
apt update && apt upgrade -y
apt install -y python3-venv python3-pip git ufw

echo "=== шаг 2: создаем пользователя для бота (если его еще нет) ==="
if ! id "$BOT_USER" &>/dev/null; then
    adduser --disabled-password --gecos "" "$BOT_USER"
fi

echo "=== шаг 3: клонируем репозиторий (от имени botuser) ==="
if [ -d "$PROJECT_PATH" ]; then
    echo "папка уже существует, подтягиваем изменения вместо клонирования"
    git config --global --add safe.directory "$PROJECT_PATH"
    su - "$BOT_USER" -c "cd $PROJECT_DIR && git pull"
else
    su - "$BOT_USER" -c "git clone $REPO_URL"
fi

echo "=== шаг 4: создаем виртуальное окружение и ставим зависимости ==="
su - "$BOT_USER" -c "
    cd $PROJECT_DIR
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
"

echo "=== шаг 5: создаем папку data/ с правильным владельцем ==="
mkdir -p "$PROJECT_PATH/data"
chown "$BOT_USER:$BOT_USER" "$PROJECT_PATH/data"

echo "=== шаг 6: создаем .env с токеном бота ==="
# -s скрывает ввод токена в терминале
read -s -p "введи токен бота от BotFather: " BOT_TOKEN
echo
echo "TELEGRAM_BOT_TOKEN=$BOT_TOKEN" > "$PROJECT_PATH/.env"
chown "$BOT_USER:$BOT_USER" "$PROJECT_PATH/.env"
chmod 600 "$PROJECT_PATH/.env"   # читать файл может только сам botuser

echo "=== шаг 7: создаем systemd-службу ==="
cat > "/etc/systemd/system/$SERVICE_NAME.service" << EOF
[Unit]
Description=Data Science Jobs Radar bot
After=network.target

[Service]
Type=simple
User=$BOT_USER
WorkingDirectory=$PROJECT_PATH
ExecStart=$PROJECT_PATH/.venv/bin/python main.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

echo "=== шаг 8: настраиваем firewall ==="
ufw allow OpenSSH
ufw --force enable   # --force чтобы не ждать подтверждения "y"

echo "=== готово! проверяем статус ==="
sleep 3
systemctl status "$SERVICE_NAME" --no-pager