# Agenda Lumiton - Calendario de Proyecciones

Este proyecto extrae automáticamente la agenda de proyecciones de películas de [Lumiton](https://lumiton.ar/agenda-presencial/) y genera archivos de calendario (ICS) que podés importar en Google Calendar, Apple Calendar, Outlook y otros.

## Cines Incluidos

- **Lumiton** - [Sgto. Cabral 2354, Munro](https://www.openstreetmap.org/search?query=Sargento%20Cabral%202354%2C%20Munro%2C%20Buenos%20Aires)
- **Cine York** - [Juan Bautista Alberdi 895, Olivos](https://www.openstreetmap.org/search?query=Juan%20Bautista%20Alberdi%20895%2C%20Olivos%2C%20Buenos%20Aires)
- **Centro Cultural Munro** - [Vélez Sarsfield 4650, Munro](https://www.openstreetmap.org/search?query=V%C3%A9lez%20Sarsfield%204650%2C%20Munro%2C%20Buenos%20Aires)

## Suscripción a Calendarios

### 🌐 Interfaz Web

**[Hacé clic acá para suscribirte a los calendarios](https://j-e-d.github.io/agenda-lumiton/)**

Página web con todos los calendarios disponibles y botones para copiar las URLs fácilmente.

### URLs de Suscripción (Método Manual)

Podés suscribirte directamente a las URLs de los archivos ICS para que tu calendario se actualice automáticamente todos los días sin que tengas que hacer nada.

#### URLs de Suscripción

Copiá la URL que prefieras y agregala a tu aplicación de calendario:

#### Calendario Completo
```
https://raw.githubusercontent.com/j-e-d/agenda-lumiton/main/calendars/all_events.ics
```

#### Calendarios por Cine
**Lumiton:**
```
https://raw.githubusercontent.com/j-e-d/agenda-lumiton/main/calendars/lumiton.ics
```

**Cine York:**
```
https://raw.githubusercontent.com/j-e-d/agenda-lumiton/main/calendars/cine_york.ics
```

**Centro Cultural Munro:**
```
https://raw.githubusercontent.com/j-e-d/agenda-lumiton/main/calendars/centro_cultural_munro.ics
```

### Descarga Manual

Si preferís descargar los archivos directamente (no se actualizan automáticamente):

- [Todas las proyecciones](calendars/all_events.ics) - Incluye eventos de los 3 cines
- [Lumiton](calendars/lumiton.ics)
- [Cine York](calendars/cine_york.ics)
- [Centro Cultural Munro](calendars/centro_cultural_munro.ics)

## Cómo Suscribirse al Calendario

### Google Calendar

**Suscripción Automática:** El calendario se actualiza solo, sin que tengas que hacer nada.

1. Copiá la URL de suscripción que querés usar (ver arriba)
2. Abrí [Google Calendar](https://calendar.google.com/)
3. Hacé clic en el botón "+" al lado de "Otros calendarios"
4. Seleccioná **Desde URL**
5. Pegá la URL del archivo ICS
6. Hacé clic en **Agregar calendario**

El calendario se actualizará automáticamente (Google Calendar sincroniza cada 24 horas aproximadamente).

**Importación Manual:** Si preferís importar una sola vez (sin actualizaciones automáticas):

1. Descargá el archivo `.ics` que prefieras
2. En Google Calendar, andá a **Configuración** → **Importar y exportar**
3. Seleccioná el archivo `.ics` descargado
4. Elegí el calendario destino e importá

### Apple Calendar (iPhone/iPad/Mac)

**Suscripción Automática:**

**Desde Mac:**
1. Abrí Calendar
2. Menú **Archivo** → **Nueva suscripción de calendario**
3. Pegá la URL de suscripción que querés usar
4. Hacé clic en **Suscribirse**
5. Configurá la frecuencia de actualización (recomendado: cada día)

**Desde iPhone/iPad:**
1. Abrí **Ajustes** → **Calendario** → **Cuentas**
2. Tocá **Agregar cuenta** → **Otra** → **Añadir calendario suscrito**
3. Pegá la URL de suscripción
4. Tocá **Siguiente** y **Guardar**

**Importación Manual:** También podés descargar el archivo `.ics` y abrirlo directamente, pero no se actualizará automáticamente.

### Outlook

**Suscripción Automática:**
1. Abrí Outlook
2. Hacé clic en **Agregar calendario** → **Desde Internet**
3. Pegá la URL de suscripción
4. El calendario se agregará y se actualizará automáticamente

**Importación Manual:** Descargá el `.ics` y andá a **Archivo** → **Abrir y exportar** → **Importar/Exportar**

### Otros Calendarios

La mayoría de las aplicaciones de calendario modernas soportan suscripciones vía URL. Buscá la opción "Suscribirse a calendario" o "Agregar calendario desde URL" en tu aplicación.

## Actualización Automática

El scraper se ejecuta automáticamente todos los días a las 9:00 UTC (6:00 AM hora Argentina) mediante GitHub Actions. Los archivos CSV y los calendarios ICS se actualizan automáticamente en este repositorio.

## Datos Disponibles

Además de los calendarios ICS, también podés acceder a los datos en formato CSV:

- [data/all_events.csv](data/all_events.csv) - Todos los eventos
- [data/lumiton.csv](data/lumiton.csv)
- [data/cine_york.csv](data/cine_york.csv)
- [data/centro_cultural_munro.csv](data/centro_cultural_munro.csv)

Cada evento incluye:
- Título de la película
- Fecha y hora
- Cine/Sala
- Sinopsis (cuando está disponible)

## Ejecutar Localmente

Si querés ejecutar el scraper en tu propia máquina:

### Requisitos
- Python 3.11 o superior
- uv (https://docs.astral.sh/uv/)

### Instalación

```bash
# Clonar el repositorio
git clone https://github.com/j-e-d/agenda-lumiton.git
cd agenda-lumiton

# Instalar uv si no lo tenés
curl -LsSf https://astral.sh/uv/install.sh | sh

# Instalar dependencias
uv sync
```

### Uso

```bash
# Ejecutar el scraper completo
uv run scraper/run.py

# O ejecutar módulos individuales
uv run scraper/scraper.py        # Solo scraping
uv run scraper/calendar_generator.py  # Solo generar calendarios
```

Los archivos generados estarán en:
- `data/` - Archivos CSV
- `calendars/` - Archivos ICS

## Contribuir

Las contribuciones son bienvenidas! Si encontrás un bug o querés agregar una funcionalidad:

1. Hacé un fork del repositorio
2. Creá una rama para tu feature (`git checkout -b feature/nueva-funcionalidad`)
3. Hacé commit de tus cambios (`git commit -m 'Agregar nueva funcionalidad'`)
4. Hacé push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Abrí un Pull Request

## Licencia

Este proyecto es de código abierto y está disponible para uso libre.

## Disclaimer

Este es un proyecto no oficial y no está afiliado con Lumiton. Los datos se extraen del sitio web público de Lumiton y se proporcionan tal como están.

## Contacto

Si tenés preguntas o sugerencias, por favor abrí un [issue](https://github.com/j-e-d/agenda-lumiton/issues).

---

**Última actualización**: 2025-10-28 23:44 UTC
