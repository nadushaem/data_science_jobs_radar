#!/bin/bash
set -e

BOT_USER="botuser"
SERVICE_NAME="data-science-jobs-radar"
PROJECT_DIR="data_science_jobs_radar"
HOME_DIR="/home/$BOT_USER"
PROJECT_PATH="$HOME_DIR/$PROJECT_DIR"

echo "=== шаг 1: подтягиваем изменения из git ==="
su - "$BOT_USER" -c "cd $PROJECT_DIR && git pull"

echo "=== шаг 2: обновляем зависимости в venv ==="
su - "$BOT_USER" -c "
    cd $PROJECT_DIR
    source .venv/bin/activate
    pip install -r requirements.txt
"

echo "=== шаг 3: перезапускаем сервис ==="
systemctl restart "$SERVICE_NAME"

echo "=== готово! проверяем статус ==="
sleep 3
systemctl status "$SERVICE_NAME" --no-pager