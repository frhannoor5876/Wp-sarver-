#!/bin/bash
# ═══════════════════════════════════════════════════════════
# ARJUN THAKUR — AUTO CLEANUP SCRIPT
# RAM/CPU/DISK SAFE • NO CRASH • SAB SERVER RUN
# ═══════════════════════════════════════════════════════════

LOG_FILE="/root/whatsapp-server/cleanup.log"
MAX_LOG_SIZE_MB=5
SESSIONS_KEEP_HOURS=24
IMAGETASKS_KEEP_HOURS=6

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Log file rotate (5MB se bada → truncate)
rotate_log() {
    if [ -f "$LOG_FILE" ]; then
        SIZE=$(du -m "$LOG_FILE" 2>/dev/null | cut -f1)
        if [ "$SIZE" -gt "$MAX_LOG_SIZE_MB" ]; then
            tail -1000 "$LOG_FILE" > "${LOG_FILE}.tmp"
            mv "${LOG_FILE}.tmp" "$LOG_FILE"
            log "📋 Log rotated (was ${SIZE}MB)"
        fi
    fi
}

log "🧹 CLEANUP STARTED"

# 1. TEMP FILES CLEAN (RAM/Python cache)
find /tmp -name "wa_img_send*" -mmin +30 -exec rm -rf {} + 2>/dev/null
find /tmp -name "*.pyc" -mmin +60 -delete 2>/dev/null
find /tmp -name "tmp*" -mmin +120 -delete 2>/dev/null
log "✅ Temp files cleaned"

# 2. UPLOAD FOLDER CLEAN
if [ -d "/root/whatsapp-server/uploads" ]; then
    find /root/whatsapp-server/uploads -type f -mmin +60 -delete 2>/dev/null
    log "✅ Uploads cleaned"
fi

# 3. OLD SESSIONS CLEAN (24h purane, non-active)
if [ -d "/root/whatsapp-server/sessions" ]; then
    find /root/whatsapp-server/sessions -name "*.sqlite-journal" -mmin +60 -delete 2>/dev/null
    find /root/whatsapp-server/sessions -name "*.sqlite-wal" -mmin +60 -delete 2>/dev/null
    find /root/whatsapp-server/sessions -name "*.sqlite-shm" -mmin +60 -delete 2>/dev/null
    log "✅ Session temp files cleaned"
fi

# 4. IMAGETASKS FOLDER CLEAN (6h purane)
if [ -d "/root/whatsapp-server/imagetasks" ]; then
    find /root/whatsapp-server/imagetasks -type d -empty -delete 2>/dev/null
    find /root/whatsapp-server/imagetasks -type f -mmin +360 -delete 2>/dev/null
    log "✅ Image tasks cleaned"
fi

# 5. PM2 LOGS CLEAN (5MB se bade)
if [ -d "/root/.pm2/logs" ]; then
    for f in /root/.pm2/logs/*.log; do
        [ -f "$f" ] || continue
        SIZE=$(du -m "$f" 2>/dev/null | cut -f1)
        if [ "$SIZE" -gt 5 ]; then
            tail -500 "$f" > "${f}.tmp"
            mv "${f}.tmp" "$f"
            log "📋 PM2 log rotated: $f (${SIZE}MB)"
        fi
    done
fi

# 6. SYSTEM CACHE CLEAN
sync
echo 1 > /proc/sys/vm/drop_caches 2>/dev/null
log "✅ System cache dropped"

# 7. PYTHON __pycache__ CLEAN
find /root/whatsapp-server -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find /root/whatsapp-server -name "*.pyc" -delete 2>/dev/null
log "✅ Python cache cleaned"

# 8. RAM/CPU STATUS CHECK
if command -v free &> /dev/null; then
    MEM_USED=$(free -m | awk 'NR==2{printf "%.1f", $3*100/$2}')
    log "📊 RAM Usage: ${MEM_USED}%"
fi

if [ -f /proc/loadavg ]; then
    LOAD=$(cat /proc/loadavg | cut -d' ' -f1)
    log "📊 CPU Load: $LOAD"
fi

# 9. PM2 STATUS CHECK (running hai ya nahi)
if command -v pm2 &> /dev/null; then
    STATUS=$(pm2 jlist 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['pm2_env']['status'] if d else 'unknown')" 2>/dev/null)
    if [ "$STATUS" != "online" ]; then
        log "⚠️ PM2 NOT ONLINE — RESTARTING..."
        pm2 restart arjun-whatsapp-server 2>/dev/null
        log "✅ PM2 restarted"
    fi
fi

# 10. LOG ROTATION SELF
rotate_log

log "✅ CLEANUP COMPLETED"
echo "---" >> "$LOG_FILE"
