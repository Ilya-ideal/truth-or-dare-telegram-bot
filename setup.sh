#!/bin/bash

echo "=== Установка бота 'Правда или Действие' на Reg.ru VPS ==="

# Обновление системы
echo "1. Обновление пакетов..."
apt update && apt upgrade -y

# Установка Python и зависимостей
echo "2. Установка Python и зависимостей..."
apt install -y python3 python3-pip python3-venv git nginx supervisor redis-server

# Настройка брандмауэра (опционально)
echo "3. Настройка брандмауэра..."
apt install -y ufw
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# Создание пользователя для бота
echo "4. Создание пользователя botuser..."
useradd -m -s /bin/bash botuser
usermod -aG sudo botuser

# Клонирование проекта
echo "5. Клонирование проекта..."
cd /home/botuser
git clone https://github.com/ваш-репозиторий/truth_or_dare_bot.git
cd truth_or_dare_bot

# Настройка Python виртуального окружения
echo "6. Настройка Python окружения..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Создание .env файла
echo "7. Создание конфигурационного файла..."
cat > .env << EOF
BOT_TOKEN=ВАШ_ТОКЕН_БОТА
ADMIN_IDS=ВАШ_ТЕЛЕГРАМ_ID
DATABASE_URL=sqlite:////home/botuser/truth_or_dare_bot/data/bot.db
REDIS_URL=redis://localhost:6379/0
EOF

# Создание директории для данных
echo "8. Создание директорий..."
mkdir -p /home/botuser/truth_or_dare_bot/data
mkdir -p /home/botuser/truth_or_dare_bot/logs

# Настройка прав
echo "9. Настройка прав доступа..."
chown -R botuser:botuser /home/botuser/truth_or_dare_bot
chmod +x /home/botuser/truth_or_dare_bot/setup.sh
chmod +x /home/botuser/truth_or_dare_bot/start_bot.py

# Настройка Systemd сервиса
echo "10. Настройка Systemd сервиса..."
cat > /etc/systemd/system/truth-or-dare-bot.service << EOF
[Unit]
Description=Truth or Dare Telegram Bot
After=network.target redis-server.service
Wants=redis-server.service

[Service]
Type=simple
User=botuser
Group=botuser
WorkingDirectory=/home/botuser/truth_or_dare_bot
Environment="PATH=/home/botuser/truth_or_dare_bot/venv/bin"
ExecStart=/home/botuser/truth_or_dare_bot/venv/bin/python /home/botuser/truth_or_dare_bot/bot.py
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=truth-or-dare-bot

# Защита сервиса
NoNewPrivileges=true
ProtectSystem=strict
PrivateTmp=true
PrivateDevices=true
ProtectHome=true
ReadWritePaths=/home/botuser/truth_or_dare_bot/data

[Install]
WantedBy=multi-user.target
EOF

# Настройка Redis
echo "11. Настройка Redis..."
sed -i 's/supervised no/supervised systemd/g' /etc/redis/redis.conf
systemctl restart redis-server
systemctl enable redis-server

# Настройка логов
echo "12. Настройка логгирования..."
cat > /etc/rsyslog.d/truth-or-dare-bot.conf << EOF
if \$programname == 'truth-or-dare-bot' then /home/botuser/truth_or_dare_bot/logs/bot.log
& stop
EOF

systemctl restart rsyslog

# Включение и запуск сервиса
echo "13. Запуск бота..."
systemctl daemon-reload
systemctl enable truth-or-dare-bot.service
systemctl start truth-or-dare-bot.service

# Настройка ротации логов
echo "14. Настройка ротации логов..."
cat > /etc/logrotate.d/truth-or-dare-bot << EOF
/home/botuser/truth_or_dare_bot/logs/bot.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 640 botuser botuser
    sharedscripts
    postrotate
        systemctl kill -s HUP truth-or-dare-bot.service
    endscript
}
EOF

echo "15. Настройка мониторинга..."
# Установка мониторинга (опционально)
apt install -y htop

echo "=== Установка завершена! ==="
echo ""
echo "Команды управления:"
echo "  systemctl status truth-or-dare-bot.service  # Статус бота"
echo "  systemctl start truth-or-dare-bot.service   # Запуск бота"
echo "  systemctl stop truth-or-dare-bot.service    # Остановка бота"
echo "  systemctl restart truth-or-dare-bot.service # Перезапуск бота"
echo "  journalctl -u truth-or-dare-bot.service -f  # Просмотр логов в реальном времени"
echo ""
echo "Файлы:"
echo "  Конфиг: /home/botuser/truth_or_dare_bot/.env"
echo "  Логи: /home/botuser/truth_or_dare_bot/logs/bot.log"
echo "  База данных: /home/botuser/truth_or_dare_bot/data/bot.db"