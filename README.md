# Sistema de Registro de Residentes y Visitas

Aplicación web simple desarrollada con Flask para registrar residentes y visitas con captura de fotos mediante la cámara del dispositivo.

## Características

- ✅ Registro de residentes con nombre, RUT y foto
- ✅ Registro de visitas con nombre, RUT, foto y tiempo de validez
- ✅ Captura de fotos usando la cámara del dispositivo
- ✅ Almacenamiento en base de datos SQLite
- ✅ Eliminación automática de visitas expiradas

## Requisitos

- Python 3.7 o superior
- Navegador web moderno con soporte para acceso a cámara (Chrome, Firefox, Edge, Safari)

## Instalación

1. Crea y activa un entorno virtual:

   **En Windows (CMD o PowerShell):**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```
   O simplemente ejecuta: `activar.bat`

   **En Windows (Git Bash):**
   ```bash
   python -m venv venv
   source venv/Scripts/activate
   ```
   O simplemente ejecuta: `./activar.sh`

   **En Linux/Mac:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
   O simplemente ejecuta: `./activar.sh`

2. Instala las dependencias:
```bash
pip install -r requirements.txt
```

3. (Opcional) Configura la carpeta de fotos creando un archivo `.env`:
```bash
# Crea un archivo .env en la raíz del proyecto
UPLOAD_FOLDER=uploads
```

   Puedes usar una ruta relativa (ej: `uploads`) o absoluta (ej: `C:\fotos` o `/var/www/fotos`). Si no defines esta variable, se usará `uploads` por defecto.

## Uso

1. Asegúrate de tener el entorno virtual activado:

   **En Windows (CMD o PowerShell):**
   ```bash
   venv\Scripts\activate
   ```
   O ejecuta: `activar.bat`

   **En Windows (Git Bash):**
   ```bash
   source venv/Scripts/activate
   ```
   O ejecuta: `./activar.sh`

   **En Linux/Mac:**
   ```bash
   source venv/bin/activate
   ```
   O ejecuta: `./activar.sh`

2. Ejecuta la aplicación:
```bash
python app.py
```

3. Abre tu navegador y ve a `http://localhost:5000`

4. Usa los botones para registrar residentes o visitas:
   - Haz clic en "Registrar Residente" o "Registrar Visita"
   - Completa el formulario con nombre y RUT
   - Para visitas, especifica las horas de validez
   - Haz clic en "Activar Cámara" y luego "Capturar Foto"
   - Envía el formulario

## Estructura del Proyecto

```
registro-residentes/
├── app.py                 # Aplicación Flask principal
├── requirements.txt       # Dependencias del proyecto
├── venv/                  # Entorno virtual (no se sube al repositorio)
├── registro.db           # Base de datos SQLite (se crea automáticamente)
├── templates/
│   └── index.html        # Interfaz web
├── uploads/              # Carpeta para almacenar fotos (se crea automáticamente)
└── README.md
```

## Configuración

### Variables de Entorno

- `UPLOAD_FOLDER`: Carpeta donde se guardarán las fotos. Puede ser una ruta relativa o absoluta. Por defecto: `fotos` (en la raíz del proyecto)

Ejemplo de archivo `.env`:
```
UPLOAD_FOLDER=/var/www/fotos
```

O en Windows:
```
UPLOAD_FOLDER=C:\fotos\residentes
```

## Notas

- Las fotos se guardan en la carpeta especificada en `UPLOAD_FOLDER` (por defecto `fotos/` en la raíz del proyecto)
- La base de datos se crea automáticamente al ejecutar la aplicación
- Las visitas expiradas pueden eliminarse llamando al endpoint `/limpiar_visitas_expiradas`
- **Importante**: El acceso a la cámara requiere:
  - Acceder a la aplicación a través de `http://localhost:5000` o `http://127.0.0.1:5000` (no usar `0.0.0.0`)
  - Permisos del navegador para acceder a la cámara
  - Un navegador moderno (Chrome, Firefox, Edge, Safari)
- Si tienes problemas con la cámara, asegúrate de estar accediendo desde `localhost` y no desde una IP externa
- El modal tiene scroll automático si el contenido es muy grande
