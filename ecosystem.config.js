module.exports = {
  apps: [{
    name: "bot2.1",
    script: "main.py",
    interpreter: "python",
    restart_delay: 5000,
    max_restarts: 20,
    watch: false,
    env: { PYTHONUNBUFFERED: "1" }
  }]
}
