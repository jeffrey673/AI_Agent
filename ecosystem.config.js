module.exports = {
  apps: [
    // ═══ PRODUCTION (3000) — 절대 kill 금지 ═══
    {
      name: "skin1004-prod",
      script: "python",
      args: "-X utf8 -m uvicorn app.main:app --host 0.0.0.0 --port 3000 --reload",
      cwd: "C:/Users/DB_PC/Desktop/python_bcj/AI_Agent",
      interpreter: "none",
      env: {
        PORT: "3000",
        PYTHONIOENCODING: "utf-8",
        PYTHONUTF8: "1",
      },
      autorestart: true,
      max_memory_restart: "2G",
      restart_delay: 3000,
      max_restarts: 10,
      min_uptime: "10s",
      out_file: "logs/pm2-prod-out.log",
      error_file: "logs/pm2-prod-error.log",
      merge_logs: true,
      time: true,
    },
    // ═══ DEVELOPMENT (3002) — 테스트/개발용 ═══
    {
      name: "skin1004-dev",
      script: "python",
      args: "-X utf8 -m uvicorn app.main:app --host 0.0.0.0 --port 3002",
      cwd: "C:/Users/DB_PC/Desktop/python_bcj/AI_Agent",
      interpreter: "none",
      env: {
        PORT: "3002",
        PYTHONIOENCODING: "utf-8",
        PYTHONUTF8: "1",
      },
      autorestart: true,
      max_memory_restart: "2G",
      restart_delay: 3000,
      max_restarts: 10,
      min_uptime: "10s",
      out_file: "logs/pm2-dev-out.log",
      error_file: "logs/pm2-dev-error.log",
      merge_logs: true,
      time: true,
    },
  ]
};
