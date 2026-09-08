PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="${VENV_PATH:-/opt/futbol}"

# Cada entorno puede sobrescribir estas variables antes de ejecutar el script.
ENV_FILE="${ENV_FILE:-$PROJECT_ROOT/.env}"
if [ -x "${VENV_PATH:-}/bin/python3" ]; then
    PYTHON_VENV="${VENV_PATH}/bin/python3"
    SERVER_ENVIRONMENT=1
elif [ -x "$PROJECT_ROOT/.venv/bin/python3" ]; then
    PYTHON_VENV="$PROJECT_ROOT/.venv/bin/python3"
    SERVER_ENVIRONMENT=0
else
    PYTHON_VENV="$(command -v python3)"
    SERVER_ENVIRONMENT=0
fi

if [ "$SERVER_ENVIRONMENT" -eq 1 ]; then
    LOG_LOCATION="/var/log"
else
    LOG_LOCATION="$PROJECT_ROOT"
fi

export ENV_FILE PYTHON_VENV PROJECT_ROOT LOG_LOCATION

CHROME_FILENAME=google-chrome-stable_current_amd64.deb
CHROME_PACKAGE_URL=https://dl.google.com/linux/direct/$CHROME_FILENAME

LOG_FILE="$LOG_LOCATION/log_diario.log"
LOG_AGENDA="$LOG_LOCATION/agenda.log"
