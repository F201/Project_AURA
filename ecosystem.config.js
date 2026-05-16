/**
 * PM2 ecosystem — AURA multi-service launcher.
 *
 * Usage:
 *   pm2 delete all && pm2 start   # clean start
 *   pm2 stop all                  # stop all
 *   pm2 restart all               # restart all
 *   pm2 logs                      # tail all logs (colour-coded per service)
 *   pm2 monit                     # live dashboard
 *   pm2 delete all                # remove from process list
 *
 * First run: npm install -g pm2
 *
 */

module.exports = {
  apps: [
    {
      name: "ai-service",
      cwd: "./ai-service",
      script: "./venv/Scripts/python.exe",
      args: "-m uvicorn app.main:app --host 0.0.0.0 --port 8001",
      watch: ["app"],
      ignore_watch: ["__pycache__", "*.pyc", "tests"],
      autorestart: true,
      max_restarts: 10,
      restart_delay: 2000,
      interpreter: "none",
      env: {
        PYTHONUNBUFFERED: "1",
        PYTHONIOENCODING: "utf-8",
      },
    },

    {
      name: "token-server",
      cwd: "./voice-agent",
      script: "./venv/Scripts/python.exe",
      args: "token_server.py",
      watch: false,
      autorestart: true,
      max_restarts: 10,
      restart_delay: 2000,
      interpreter: "none",
      env: {
        PYTHONUNBUFFERED: "1",
        PYTHONIOENCODING: "utf-8",
      },
    },

    {
      name: "voice-agent",
      cwd: "./voice-agent",
      script: "python",
      args: "agent.py dev",
      watch: false,
      autorestart: true,
      windowsHide: true,
      max_restarts: 10,
      restart_delay: 3000,
      interpreter: "none",
      env: {
        PYTHONUNBUFFERED: "1",
        PYTHONIOENCODING: "utf-8",
      },
    },

    {
      name: "dashboard",
      cwd: "./dashboard",
      script: "cmd",
      args: "/c npm run dev -- --host",
      watch: false,
      autorestart: true,
      max_restarts: 5,
      restart_delay: 3000,
      interpreter: "none",
    },
  ],
};
