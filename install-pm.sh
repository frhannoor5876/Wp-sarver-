#!/bin/bash
# ═══════════════════════════════════════════════════════════
# ARJUN THAKUR — PM2 SETUP + AUTO CLEANUP INSTALLER
# ═══════════════════════════════════════════════════════════

echo "🚀 Starting PM2 + Cleanup Setup..."

# 1. PM2 INSTALL (agar nahi hai)
if ! command -v pm2 &> /dev/null; then
    echo "📦 Installing PM2..."
    npm install -g pm2
    npm install -g pm2-logrotate
fi

# 2. PM2 LOGROTATE CONFIGURE
pm2 install pm2-logrotate 2>/dev/null
pm2 set pm2-logrotate:max_size 10M
pm2 set pm2-logrotate:retain 3
pm2 set pm2-logrotate:compress true
pm2 set pm2-logrotate:rotateInterval '0 0 * * *'

# 3. DIRECTORIES
mkdir -p /root/whatsapp-server/logs
mkdir -p /root/whatsapp-server/uploads
mkdir -p /root/whatsapp-server/sessions
mkdir -p /root/whatsapp-server/imagetasks

# 4. CLEANUP SCRIPT EXECUTE PERMISSION
chmod +x /root/whatsapp-server/cleanup.sh

# 5. CRON JOB (har 10 min cleanup)
CRON_LINE="*/10 * * * * /root/whatsapp-server/cleanup.sh > /dev/null 2>&1"
(crontab -l 2>/dev/null | grep -v "cleanup.sh"; echo "$CRON_LINE") | crontab -
echo "✅ Cron job added (every 10 min)"

# 6. PM2 START WITH CONFIG
cd /root/whatsapp-server
pm2 delete arjun-whatsapp-server 2>/dev/null
pm2 start ecosystem.config.js
pm2 save

# 7. PM2 STARTUP ON BOOT
pm2 startup systemd -u root --hp /root 2>/dev/null | grep "sudo" | bash 2>/dev/null
pm2 save

echo ""
echo "═══════════════════════════════════════════════════════"
echo "✅ SETUP COMPLETE!"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "📊 Useful Commands:"
echo "  pm2 status              — Sab processes dekho"
echo "  pm2 logs arjun-whatsapp-server  — Live logs"
echo "  pm2 monit               — Real-time CPU/RAM"
echo "  pm2 restart arjun-whatsapp-server  — Manual restart"
echo "  pm2 flush               — Logs clear karo"
echo "  bash cleanup.sh         — Manual cleanup"
echo ""
echo "🔥 Auto Features:"
echo "  • RAM > 800MB → auto restart"
echo "  • Crash → auto restart (5s delay)"
echo "  • Roz 4 AM → auto restart"
echo "  • Har 10 min → auto cleanup"
echo "  • Logs rotate @ 10MB"
echo "  • Boot pe auto start"
echo ""
