#!/bin/bash
echo "Activando entorno virtual..."

# Detectar si estamos en Windows (Git Bash) o Linux/Mac
if [ -f "venv/Scripts/activate" ]; then
    # Windows (Git Bash)
    source venv/Scripts/activate
elif [ -f "venv/bin/activate" ]; then
    # Linux/Mac
    source venv/bin/activate
else
    echo "Error: No se encontró el entorno virtual. Asegúrate de haberlo creado primero."
    exit 1
fi

echo "Entorno virtual activado!"
echo ""
echo "Para ejecutar la aplicacion, usa: python app.py"
echo "Para desactivar el entorno virtual, usa: deactivate"
exec bash

