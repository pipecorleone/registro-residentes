from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file, abort
from datetime import datetime, timedelta
import sqlite3
import os
import base64
import json
import shutil
import re
from dotenv import load_dotenv

# Cargar variables de entorno desde archivo .env
load_dotenv()

app = Flask(__name__)

# Obtener carpeta de uploads desde variable de entorno
# Si no está configurada, usar carpeta 'fotos' en la raíz del proyecto
upload_folder_env = os.getenv('UPLOAD_FOLDER')
if upload_folder_env:
    app.config['UPLOAD_FOLDER'] = upload_folder_env
else:
    # Ruta por defecto en la raíz del proyecto
    base_dir = os.path.dirname(os.path.abspath(__file__))
    app.config['UPLOAD_FOLDER'] = os.path.join(base_dir, 'fotos')

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Crear directorio de uploads si no existe
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def limpiar_nombre_carpeta(nombre):
    """
    Limpia el nombre de una carpeta eliminando caracteres especiales.
    
    Esta función toma un nombre y lo convierte en un formato seguro para usar
    como nombre de carpeta, reemplazando espacios y caracteres especiales por guiones bajos.
    
    Args:
        nombre (str): El nombre original que se quiere limpiar
        
    Returns:
        str: El nombre limpio sin caracteres especiales, con espacios y guiones
             reemplazados por guiones bajos
             
    Ejemplo:
        "Juan Pérez" -> "Juan_Perez"
        "María-González" -> "Maria_Gonzalez"
    """
    # Eliminar todos los caracteres que no sean letras, números, espacios o guiones
    nombre_limpio = re.sub(r'[^\w\s-]', '', nombre)
    # Reemplazar espacios y guiones múltiples por un solo guión bajo
    nombre_limpio = re.sub(r'[-\s]+', '_', nombre_limpio)
    # Eliminar guiones bajos al inicio y final
    return nombre_limpio.strip('_')

def init_db():
    """
    Inicializa la base de datos SQLite creando las tablas necesarias.
    
    Esta función crea las tablas 'residentes' y 'visitas' si no existen,
    y también agrega la columna 'carpeta_path' a las tablas existentes
    para mantener compatibilidad con versiones anteriores del sistema.
    
    Las tablas creadas son:
    - residentes: Almacena información de residentes registrados
    - visitas: Almacena información de visitas con fecha de expiración
    
    No retorna ningún valor, solo crea/modifica la estructura de la base de datos.
    """
    conn = sqlite3.connect('registro.db')
    c = conn.cursor()
    
    # Crear tabla de residentes con sus campos principales
    c.execute('''CREATE TABLE IF NOT EXISTS residentes
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  nombre TEXT NOT NULL,
                  rut TEXT NOT NULL UNIQUE,
                  foto_path TEXT NOT NULL,
                  carpeta_path TEXT NOT NULL,
                  fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Crear tabla de visitas con fecha de expiración
    c.execute('''CREATE TABLE IF NOT EXISTS visitas
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  nombre TEXT NOT NULL,
                  rut TEXT NOT NULL,
                  foto_path TEXT NOT NULL,
                  carpeta_path TEXT NOT NULL,
                  fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  fecha_expiracion TIMESTAMP NOT NULL)''')
    
    # Migración: Agregar columna carpeta_path si no existe (para compatibilidad)
    try:
        c.execute('ALTER TABLE residentes ADD COLUMN carpeta_path TEXT')
    except sqlite3.OperationalError:
        pass  # La columna ya existe, no hacer nada
    
    try:
        c.execute('ALTER TABLE visitas ADD COLUMN carpeta_path TEXT')
    except sqlite3.OperationalError:
        pass  # La columna ya existe, no hacer nada
    
    conn.commit()
    conn.close()

@app.route('/')
def index():
    """
    Ruta principal de la aplicación.
    
    Muestra la página de inicio con los formularios para registrar
    residentes o visitas.
    
    Returns:
        HTML: Renderiza el template index.html con el formulario principal
    """
    return render_template('index.html')

@app.route('/captura_fotos')
def captura_fotos():
    """
    Muestra la página de captura de fotos.
    
    Esta ruta recibe los datos del formulario (nombre, RUT, tipo) y opcionalmente
    un registro_id si se está retomando las fotos de un registro existente.
    Renderiza la página donde el usuario puede capturar múltiples fotos.
    
    Parámetros GET:
        tipo (str): Tipo de registro ('residente' o 'visita')
        nombre (str): Nombre de la persona
        rut (str): RUT de la persona
        fecha_limite (str, opcional): Fecha límite para visitas (formato datetime-local)
        registro_id (str, opcional): ID del registro si se está retomando fotos
        
    Returns:
        HTML: Renderiza el template captura_fotos.html con los datos proporcionados
    """
    tipo = request.args.get('tipo', 'residente')
    nombre = request.args.get('nombre', '')
    rut = request.args.get('rut', '')
    fecha_limite = request.args.get('fecha_limite', '')
    registro_id = request.args.get('registro_id', '')
    
    return render_template('captura_fotos.html', 
                         tipo=tipo, 
                         nombre=nombre, 
                         rut=rut, 
                         fecha_limite=fecha_limite,
                         registro_id=registro_id)

@app.route('/registrar_residente', methods=['POST'])
def registrar_residente():
    """
    Registra un nuevo residente o actualiza las fotos de uno existente.
    
    Esta función procesa el registro de un residente con sus fotos. Puede crear
    un nuevo registro o actualizar las fotos de un registro existente si se
    proporciona un registro_id (cuando se retoman las fotos).
    
    Proceso:
    1. Valida los datos recibidos (nombre, RUT, fotos)
    2. Crea o encuentra la carpeta del residente
    3. Guarda todas las fotos en formato JPG dentro de la carpeta
    4. Crea un archivo datos.json con la información del residente
    5. Guarda o actualiza el registro en la base de datos
    
    Body JSON esperado:
        nombre (str): Nombre del residente
        rut (str): RUT del residente (sin puntos ni guión)
        fotos (list): Lista de fotos en formato base64
        registro_id (str, opcional): ID del registro si se está actualizando
        
    Returns:
        JSON: Respuesta con success=True/False y un mensaje descriptivo
        
    Status codes:
        200: Registro exitoso
        400: Error de validación o RUT duplicado
        404: Registro no encontrado (al actualizar)
        500: Error del servidor
    """
    try:
        data = request.json
        nombre = data.get('nombre')
        rut = data.get('rut')
        fotos_base64 = data.get('fotos', [])
        registro_id = data.get('registro_id')
        
        # Validar que se proporcionen los datos requeridos
        if not nombre or not rut:
            return jsonify({'success': False, 'message': 'Faltan datos requeridos'}), 400
        
        # Validar que haya al menos una foto
        if not fotos_base64 or len(fotos_base64) == 0:
            return jsonify({'success': False, 'message': 'Debes capturar al menos una foto'}), 400
        
        conn = sqlite3.connect('registro.db')
        c = conn.cursor()
        
        # Si hay registro_id, es una actualización (retomar fotos)
        if registro_id:
            # Buscar la carpeta existente del residente
            c.execute('SELECT carpeta_path FROM residentes WHERE id = ?', (registro_id,))
            result = c.fetchone()
            if result:
                carpeta_persona = result[0]
            else:
                conn.close()
                return jsonify({'success': False, 'message': 'Registro no encontrado'}), 404
        else:
            # Crear nueva subcarpeta para el residente
            nombre_carpeta = f"{limpiar_nombre_carpeta(nombre)}_{rut}"
            carpeta_persona = os.path.join(app.config['UPLOAD_FOLDER'], nombre_carpeta)
            os.makedirs(carpeta_persona, exist_ok=True)
        
        # Guardar todas las fotos en la subcarpeta
        foto_paths = []
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for i, foto_base64 in enumerate(fotos_base64):
            # Decodificar la imagen base64 (eliminar el prefijo data:image/jpeg;base64,)
            foto_data = base64.b64decode(foto_base64.split(',')[1])
            foto_filename = f"foto_{i+1:02d}.jpg"
            foto_path = os.path.join(carpeta_persona, foto_filename)
            
            # Guardar la foto en el sistema de archivos
            with open(foto_path, 'wb') as f:
                f.write(foto_data)
            
            foto_paths.append(foto_path)
        
        # Crear archivo de datos en JSON dentro de la carpeta
        datos_persona = {
            'nombre': nombre,
            'rut': rut,
            'tipo': 'residente',
            'fecha_registro': datetime.now().isoformat(),
            'total_fotos': len(fotos_base64)
        }
        
        datos_path = os.path.join(carpeta_persona, 'datos.json')
        with open(datos_path, 'w', encoding='utf-8') as f:
            json.dump(datos_persona, f, indent=2, ensure_ascii=False)
        
        # Guardar o actualizar en la base de datos
        try:
            if registro_id:
                # Actualizar registro existente con nueva foto principal
                c.execute('''UPDATE residentes SET foto_path = ? WHERE id = ?''', 
                         (foto_paths[0], registro_id))
                conn.commit()
                mensaje = f'Fotos actualizadas exitosamente con {len(fotos_base64)} foto(s)'
            else:
                # Insertar nuevo registro en la base de datos
                c.execute('''INSERT INTO residentes (nombre, rut, foto_path, carpeta_path)
                             VALUES (?, ?, ?, ?)''', (nombre, rut, foto_paths[0], carpeta_persona))
                conn.commit()
                mensaje = f'Residente registrado exitosamente con {len(fotos_base64)} foto(s)'
            
            return jsonify({'success': True, 'message': mensaje})
        except sqlite3.IntegrityError:
            # El RUT ya está registrado (solo aplica para nuevos registros)
            return jsonify({'success': False, 'message': 'El RUT ya está registrado'}), 400
        finally:
            conn.close()
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/registrar_visita', methods=['POST'])
def registrar_visita():
    """
    Registra una nueva visita o actualiza las fotos de una existente.
    
    Similar a registrar_residente, pero para visitas. Incluye la fecha y hora
    límite de validez de la visita. Las visitas tienen una fecha de expiración
    después de la cual se pueden eliminar automáticamente.
    
    Proceso:
    1. Valida los datos recibidos (nombre, RUT, fotos, fecha límite)
    2. Convierte la fecha límite de string a datetime
    3. Crea o encuentra la carpeta de la visita
    4. Guarda todas las fotos en formato JPG
    5. Crea archivo datos.json con información incluyendo fecha de expiración
    6. Guarda o actualiza el registro en la base de datos
    
    Body JSON esperado:
        nombre (str): Nombre de la visita
        rut (str): RUT de la visita (sin puntos ni guión)
        fotos (list): Lista de fotos en formato base64
        fecha_limite (str): Fecha y hora límite en formato 'YYYY-MM-DDTHH:MM'
        registro_id (str, opcional): ID del registro si se está actualizando
        
    Returns:
        JSON: Respuesta con success=True/False y un mensaje descriptivo
        
    Status codes:
        200: Registro exitoso
        400: Error de validación o formato de fecha inválido
        404: Registro no encontrado (al actualizar)
        500: Error del servidor
    """
    try:
        data = request.json
        nombre = data.get('nombre')
        rut = data.get('rut')
        fotos_base64 = data.get('fotos', [])
        fecha_limite_str = data.get('fecha_limite', '')
        registro_id = data.get('registro_id')
        
        # Validar datos requeridos
        if not nombre or not rut:
            return jsonify({'success': False, 'message': 'Faltan datos requeridos'}), 400
        
        if not fotos_base64 or len(fotos_base64) == 0:
            return jsonify({'success': False, 'message': 'Debes capturar al menos una foto'}), 400
        
        if not fecha_limite_str:
            return jsonify({'success': False, 'message': 'Debes especificar una fecha y hora límite'}), 400
        
        # Convertir fecha límite de string a objeto datetime
        try:
            # Reemplazar 'T' por espacio para compatibilidad con fromisoformat
            fecha_expiracion = datetime.fromisoformat(fecha_limite_str.replace('T', ' '))
        except ValueError:
            return jsonify({'success': False, 'message': 'Formato de fecha inválido'}), 400
        
        conn = sqlite3.connect('registro.db')
        c = conn.cursor()
        
        # Si hay registro_id, es una actualización (retomar fotos)
        if registro_id:
            # Buscar la carpeta existente de la visita
            c.execute('SELECT carpeta_path FROM visitas WHERE id = ?', (registro_id,))
            result = c.fetchone()
            if result:
                carpeta_persona = result[0]
            else:
                conn.close()
                return jsonify({'success': False, 'message': 'Registro no encontrado'}), 404
        else:
            # Crear nueva subcarpeta para la visita
            nombre_carpeta = f"{limpiar_nombre_carpeta(nombre)}_{rut}"
            carpeta_persona = os.path.join(app.config['UPLOAD_FOLDER'], nombre_carpeta)
            os.makedirs(carpeta_persona, exist_ok=True)
        
        # Guardar todas las fotos en la subcarpeta
        foto_paths = []
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for i, foto_base64 in enumerate(fotos_base64):
            # Decodificar imagen base64
            foto_data = base64.b64decode(foto_base64.split(',')[1])
            foto_filename = f"foto_{i+1:02d}.jpg"
            foto_path = os.path.join(carpeta_persona, foto_filename)
            
            # Guardar foto en el sistema de archivos
            with open(foto_path, 'wb') as f:
                f.write(foto_data)
            
            foto_paths.append(foto_path)
        
        # Crear archivo de datos en JSON con información de la visita
        datos_persona = {
            'nombre': nombre,
            'rut': rut,
            'tipo': 'visita',
            'fecha_registro': datetime.now().isoformat(),
            'fecha_expiracion': fecha_expiracion.isoformat(),
            'total_fotos': len(fotos_base64)
        }
        
        datos_path = os.path.join(carpeta_persona, 'datos.json')
        with open(datos_path, 'w', encoding='utf-8') as f:
            json.dump(datos_persona, f, indent=2, ensure_ascii=False)
        
        # Guardar o actualizar en la base de datos
        if registro_id:
            # Actualizar registro existente con nueva foto y fecha de expiración
            c.execute('''UPDATE visitas SET foto_path = ?, fecha_expiracion = ? WHERE id = ?''', 
                     (foto_paths[0], fecha_expiracion, registro_id))
            conn.commit()
            fecha_formateada = fecha_expiracion.strftime('%d/%m/%Y %H:%M')
            mensaje = f'Fotos actualizadas exitosamente con {len(fotos_base64)} foto(s). Válida hasta {fecha_formateada}'
        else:
            # Insertar nuevo registro de visita
            c.execute('''INSERT INTO visitas (nombre, rut, foto_path, carpeta_path, fecha_expiracion)
                         VALUES (?, ?, ?, ?, ?)''', (nombre, rut, foto_paths[0], carpeta_persona, fecha_expiracion))
            conn.commit()
            fecha_formateada = fecha_expiracion.strftime('%d/%m/%Y %H:%M')
            mensaje = f'Visita registrada exitosamente con {len(fotos_base64)} foto(s). Válida hasta {fecha_formateada}'
        
        conn.close()
        return jsonify({'success': True, 'message': mensaje})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/foto/<int:registro_id>/<tipo>')
def servir_foto(registro_id, tipo):
    """
    Sirve la foto principal de un registro como imagen HTTP.
    
    Esta función permite mostrar las fotos de residentes y visitas en la
    página de listado. Busca la ruta de la foto principal en la base de
    datos y la sirve como archivo JPEG.
    
    Args:
        registro_id (int): ID del registro (residente o visita)
        tipo (str): Tipo de registro ('residente' o 'visita')
        
    Returns:
        File: Archivo de imagen JPEG o error 404 si no se encuentra
        
    Status codes:
        200: Foto encontrada y servida exitosamente
        404: Registro no encontrado o archivo de foto no existe
    """
    try:
        conn = sqlite3.connect('registro.db')
        c = conn.cursor()
        
        # Buscar la ruta de la foto según el tipo de registro
        if tipo == 'residente':
            c.execute('SELECT foto_path FROM residentes WHERE id = ?', (registro_id,))
        else:
            c.execute('SELECT foto_path FROM visitas WHERE id = ?', (registro_id,))
        
        result = c.fetchone()
        conn.close()
        
        # Verificar que existe el registro y el archivo de foto
        if result and result[0] and os.path.exists(result[0]):
            # Servir el archivo de imagen
            return send_file(result[0], mimetype='image/jpeg')
        else:
            # Retornar error 404 si no se encuentra
            abort(404)
    except Exception as e:
        # En caso de cualquier error, retornar 404
        abort(404)

@app.route('/listar_registros')
def listar_registros():
    """
    Muestra la página con todos los registros de residentes y visitas.
    
    Esta función obtiene todos los residentes registrados y todas las visitas
    que aún no han expirado (fecha_expiracion > fecha actual). Los datos se
    formatean en diccionarios para facilitar su uso en el template.
    
    Las visitas expiradas no se muestran en esta lista, pero pueden eliminarse
    manualmente o usando el endpoint limpiar_visitas_expiradas.
    
    Returns:
        HTML: Renderiza el template listar_registros.html con las listas de
              residentes y visitas formateadas
        
    Status codes:
        200: Lista generada exitosamente
        500: Error al acceder a la base de datos
    """
    try:
        conn = sqlite3.connect('registro.db')
        c = conn.cursor()
        
        # Obtener todos los residentes ordenados por fecha de registro (más recientes primero)
        c.execute('''SELECT id, nombre, rut, foto_path, carpeta_path, fecha_registro 
                     FROM residentes ORDER BY fecha_registro DESC''')
        residentes = c.fetchall()
        
        # Obtener solo las visitas que aún no han expirado
        c.execute('''SELECT id, nombre, rut, foto_path, carpeta_path, fecha_registro, fecha_expiracion 
                     FROM visitas WHERE fecha_expiracion > ? ORDER BY fecha_registro DESC''', (datetime.now(),))
        visitas = c.fetchall()
        
        conn.close()
        
        # Formatear datos de residentes en diccionarios para el template
        residentes_list = []
        for r in residentes:
            residentes_list.append({
                'id': r[0],
                'nombre': r[1],
                'rut': r[2],
                'foto_path': r[3],
                'carpeta_path': r[4],
                'fecha_registro': r[5]
            })
        
        # Formatear datos de visitas en diccionarios para el template
        visitas_list = []
        for v in visitas:
            visitas_list.append({
                'id': v[0],
                'nombre': v[1],
                'rut': v[2],
                'foto_path': v[3],
                'carpeta_path': v[4],
                'fecha_registro': v[5],
                'fecha_expiracion': v[6]
            })
        
        return render_template('listar_registros.html', 
                             residentes=residentes_list, 
                             visitas=visitas_list)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/limpiar_visitas_expiradas', methods=['POST'])
def limpiar_visitas_expiradas():
    """
    Elimina automáticamente todas las visitas que han expirado.
    
    Esta función busca todas las visitas cuya fecha_expiracion es anterior
    a la fecha/hora actual y las elimina tanto de la base de datos como
    sus carpetas completas del sistema de archivos (incluyendo todas las fotos).
    
    Puede ser llamada manualmente o programada para ejecutarse periódicamente.
    
    Returns:
        JSON: Respuesta con success=True/False y el número de visitas eliminadas
        
    Ejemplo de respuesta:
        {'success': True, 'eliminadas': 5}
        
    Status codes:
        200: Proceso completado (puede haber eliminado 0 o más visitas)
        500: Error al procesar la limpieza
    """
    try:
        conn = sqlite3.connect('registro.db')
        c = conn.cursor()
        
        # Obtener todas las visitas expiradas con sus rutas de carpeta
        c.execute('''SELECT carpeta_path FROM visitas 
                     WHERE fecha_expiracion < ?''', (datetime.now(),))
        carpetas_expiradas = c.fetchall()
        
        # Eliminar carpetas completas del sistema de archivos
        for (carpeta_path,) in carpetas_expiradas:
            try:
                if os.path.exists(carpeta_path):
                    # Eliminar carpeta completa con todas sus fotos
                    shutil.rmtree(carpeta_path)
            except Exception as e:
                # Registrar error pero continuar con otras carpetas
                print(f"Error al eliminar carpeta {carpeta_path}: {e}")
        
        # Eliminar registros de visitas expiradas de la base de datos
        c.execute('''DELETE FROM visitas WHERE fecha_expiracion < ?''', (datetime.now(),))
        eliminadas = c.rowcount
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'eliminadas': eliminadas})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/eliminar_registro/<tipo>/<int:registro_id>', methods=['DELETE'])
def eliminar_registro(tipo, registro_id):
    """
    Elimina permanentemente un registro (residente o visita) y toda su información.
    
    Esta función elimina completamente un registro de la base de datos y también
    elimina la carpeta completa del sistema de archivos que contiene todas las
    fotos y el archivo datos.json del registro.
    
    Es una operación destructiva que no se puede deshacer.
    
    Args:
        tipo (str): Tipo de registro a eliminar ('residente' o 'visita')
        registro_id (int): ID del registro a eliminar
        
    Returns:
        JSON: Respuesta con success=True/False y un mensaje descriptivo
        
    Status codes:
        200: Registro eliminado exitosamente
        400: Tipo de registro inválido
        404: Registro no encontrado
        500: Error al eliminar el registro
    """
    try:
        conn = sqlite3.connect('registro.db')
        c = conn.cursor()
        
        # Obtener la ruta de la carpeta del registro según su tipo
        if tipo == 'residente':
            c.execute('SELECT carpeta_path FROM residentes WHERE id = ?', (registro_id,))
        elif tipo == 'visita':
            c.execute('SELECT carpeta_path FROM visitas WHERE id = ?', (registro_id,))
        else:
            return jsonify({'success': False, 'message': 'Tipo inválido'}), 400
        
        result = c.fetchone()
        if not result:
            return jsonify({'success': False, 'message': 'Registro no encontrado'}), 404
        
        carpeta_path = result[0]
        
        # Eliminar carpeta completa del sistema de archivos (incluye todas las fotos)
        if carpeta_path and os.path.exists(carpeta_path):
            try:
                shutil.rmtree(carpeta_path)
            except Exception as e:
                # Registrar error pero continuar con la eliminación de la BD
                print(f"Error al eliminar carpeta {carpeta_path}: {e}")
        
        # Eliminar registro de la base de datos
        if tipo == 'residente':
            c.execute('DELETE FROM residentes WHERE id = ?', (registro_id,))
        else:
            c.execute('DELETE FROM visitas WHERE id = ?', (registro_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': f'{tipo.capitalize()} eliminado exitosamente'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/retomar_fotos/<tipo>/<int:registro_id>')
def retomar_fotos(tipo, registro_id):
    """
    Permite retomar las fotos de un registro existente.
    
    Esta función elimina las fotos anteriores de un registro (manteniendo la
    carpeta y el archivo datos.json) y redirige al usuario a la página de
    captura de fotos con los datos del registro prellenados. Esto permite
    capturar nuevas fotos que reemplazarán a las anteriores.
    
    Proceso:
    1. Obtiene los datos del registro desde la base de datos
    2. Elimina todas las fotos existentes (archivos foto_*.jpg)
    3. Mantiene la carpeta y el archivo datos.json
    4. Redirige a la página de captura con los datos del registro
    
    Args:
        tipo (str): Tipo de registro ('residente' o 'visita')
        registro_id (int): ID del registro cuyas fotos se quieren retomar
        
    Returns:
        Redirect: Redirección a /captura_fotos con los parámetros del registro
        
    Status codes:
        302: Redirección exitosa a la página de captura
        400: Tipo de registro inválido
        404: Registro no encontrado
        500: Error al procesar la solicitud
    """
    try:
        conn = sqlite3.connect('registro.db')
        c = conn.cursor()
        
        # Obtener información del registro según su tipo
        if tipo == 'residente':
            c.execute('SELECT nombre, rut, carpeta_path FROM residentes WHERE id = ?', (registro_id,))
        elif tipo == 'visita':
            c.execute('SELECT nombre, rut, fecha_expiracion, carpeta_path FROM visitas WHERE id = ?', (registro_id,))
        else:
            return jsonify({'success': False, 'message': 'Tipo inválido'}), 400
        
        result = c.fetchone()
        if not result:
            return jsonify({'success': False, 'message': 'Registro no encontrado'}), 404
        
        nombre = result[0]
        rut = result[1]
        # La carpeta_path está en diferentes posiciones según el tipo
        carpeta_path = result[2] if tipo == 'residente' else result[3]
        
        # Eliminar solo las fotos anteriores (mantener carpeta y datos.json)
        if carpeta_path and os.path.exists(carpeta_path):
            for archivo in os.listdir(carpeta_path):
                # Eliminar solo archivos que empiecen con 'foto_' y terminen en '.jpg'
                if archivo.startswith('foto_') and archivo.endswith('.jpg'):
                    try:
                        os.remove(os.path.join(carpeta_path, archivo))
                    except Exception as e:
                        print(f"Error al eliminar foto {archivo}: {e}")
        
        # Construir parámetros para la redirección a la página de captura
        params = {
            'tipo': tipo,
            'nombre': nombre,
            'rut': rut,
            'registro_id': str(registro_id)
        }
        
        # Si es una visita, agregar la fecha límite formateada
        if tipo == 'visita':
            fecha_expiracion = result[2]
            # Convertir datetime a formato datetime-local para el input HTML
            if isinstance(fecha_expiracion, str):
                fecha_expiracion = datetime.fromisoformat(fecha_expiracion.replace(' ', 'T'))
            fecha_formato = fecha_expiracion.strftime('%Y-%m-%dT%H:%M')
            params['fecha_limite'] = fecha_formato
        
        # Construir query string y redirigir
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return redirect(f'/captura_fotos?{query_string}')
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)

