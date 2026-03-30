module.exports = {
  apps: [{
    name: "skin1004-ai",
    script: "python",
    args: "-X utf8 -m uvicorn app.main:app --host 0.0.0.0 --port 3000 --reload",
    cwd: "C:/Users/DB_PC/Desktop/python_bcj/AI_Agent",
    env: {
      PORT: "3000",
    },
    // Auto-restart on crash
    autorestart: true,
    // Restart if memory exceeds 2GB
    max_memory_restart: "2G",
    // Wait 3s before restart
    restart_delay: 3000,
    // Max 10 restarts in 1 minute (prevent crash loop)
    max_restarts: 10,
    min_uptime: "10s",
    // Log files
    out_file: "logs/pm2-out.log",
    error_file: "logs/pm2-error.log",
    merge_logs: true,
    // Timestamp logs
    time: true,
  }]
};
