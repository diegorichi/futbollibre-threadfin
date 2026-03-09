source `pwd`/config.sh

# 1. Actualizar el sistema
apt update && apt upgrade -y

# 2. Instalar Python, Pip y herramientas de red
apt install -y python3 python3-pip python3-venv git curl wget xvfb ffmpeg

# 2. Crear el Entorno Virtual (VENV) si no existe
if [ ! -d "$VENV_PATH" ]; then
    python3 -m venv $VENV_PATH
    echo "Entorno virtual creado en $VENV_PATH"
fi


# 3. Instalar Google Chrome y sus dependencias de sistema
# Esto instala el navegador Y todas las librerías necesarias para correr sin monitor
wget $CHROME_PACKAGE_URL
apt install -y ./$CHROME_FILENAME

# 3. Instalar librer  as de Python en el VENV
$VENV_PATH/bin/pip install --upgrade pip
$VENV_PATH/bin/pip install selenium webdriver-manager
$VENV_PATH/bin/pip install python-dotenv
# 4. Crear el script lanzador (Shell Script)
LANZADOR="`pwd`/update-futbollibre.sh"
chmod +x "$LANZADOR"

CRON_JOB="0 8 * * * /bin/bash $LANZADOR >> $LOG_FILE 2>&1"

# Solo agregamos si no existe ya en el crontab actual
(crontab -l 2>/dev/null | grep -Fv "$LANZADOR"; echo "$CRON_JOB") | crontab -

echo " Instalacion completada con exito."

rm $CHROME_FILENAME
