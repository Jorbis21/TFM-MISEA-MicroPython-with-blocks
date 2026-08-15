# TFM MISEA | MicroPython with blocks.

[![License: Non-Commercial](https://img.shields.io/badge/License-Non_Commercial-red.svg)](#license)
### TECHNOLOGY WITH PURPOSE: Design of a system that enables block-based programming learning for people with visual impairment.

Desktop application designed so that blind or low-vision people can program the BBC Micro:bit board without needing to see a screen. Code blocks are represented as physical blocks with braille stickers and QR codes: the camera detects them, and the program automatically translates them into working MicroPython code through a pushdown automaton, with voice prompts whenever a variable is needed.

_Developed in collaboration with ONCE (Spanish National Organization of the Blind)._

**This repository has several folders; the one with the main project is QrReader.**

The BrailleReader folder was an attempt at computer vision using high-contrast braille for code generation. It was dropped due to the difficulty of detecting some letters. Should anyone want to develop it further, QR-style corner squares could be used for simpler reading.

Lastly, the QrReader.old folder was the first semi-functional version of the application, without important elements such as the pushdown automaton or voice control.

### What it does

- **Camera-based block reading**: place the blocks in the desired order, the app detects the physical layout through computer vision and generates the corresponding MicroPython code using a pushdown automaton.
- **Voice control**: every action (capture, send to the board, explain the code, read aloud, review) can be triggered by voice, transcribed locally with Whisper.
- **Reading results aloud**: the board can send values back to the computer by voice while the program runs, read aloud.
- **AI code explanation**: in plain, jargon-free language, using Gemini if there's a connection, a local AI (Ollama + phi3) if there isn't, or a literal reading of the code as a last resort.
- **Direct upload to the board**: the generated code is uploaded to the Micro:bit over USB with a single voice command.
- **QR generator**: creates and prints to PDF the QRs for any block in the dictionary, at whatever size is needed to use them on physical blocks.
- **Dictionary editor**: add, edit or delete available blocks without touching any code.
- **Bilingual** (Spanish / English), with its own voices and audio cache for each language.
- **High-contrast mode** for low vision.

### Download

The application needs no installation: download it, unzip it, and run it.

The portable builds for Windows, Linux and Mac are in the repository's [Releases section](https://github.com/Jorbis21/TFM_MISEA/releases/). Each operating system has two files:

- `MicroPython_with_blocks-<os>.zip` — the application itself, with the local AI engine (Ollama) already included.
- `MicroPython_with_blocks-<os>-phi3-model.zip` — the local AI model (phi3), separate because it exceeds GitHub's single-file size limit.

To have local AI working from the very first launch, unzip both files, first the application one and then the model, inside the application's folder. If you're only interested in the Gemini explanation (with an internet connection) or the literal code reading, the first zip is enough, but a `.env` file is required in the folder.

### Cloud AI explanation

To use Gemini for AI explanations, create a `.env` file next to the executable with:

```
GEMINI_API_KEY=your_key_here
```

To get this key, go to [Google AI Studio](https://aistudio.google.com/) and generate your own key there. Without this file, the app still works, going straight to the local AI or the literal reading instead.

### Running from source

Requires Python 3.12 or higher.

```
pip install -r requirements.txt
python src/main.py
```

It also requires having ollama installed with the phi3 model, as well as the `.env` file next to main.py.

### Project structure

The project follows an MVC architecture:

```
src/
├── controllers/   # Orchestrate models and views, without touching the interface directly
├── models/        # Business logic: vision, translator, voice, AI, serial...
├── views/         # Interface (PyQt6)
├── services/      # Cross-cutting services (audio)
└── utils/         # Shared utilities: language, constants, paths...
```

## License

This project is licensed under the **PolyForm Noncommercial License 1.0.0**.

**What you CAN do:**

- Use, modify and distribute this code for personal projects.
- Use it for educational or research purposes.
- Use it within non-profit organizations.

**What you CANNOT do:**

- Use this code (or modified versions of it) in commercial products.
- Sell it or offer it as part of a paid service.
- Use it within the internal environment of a for-profit company.

If you're interested in using this software for commercial purposes, please contact me at **[javierorbis@gmail.com]** to negotiate a commercial license.

You can read the full legal text in the [LICENSE](https://github.com/Jorbis21/TFM_MISEA/blob/main/LICENSE) file of this repository.

# TFM MISEA | MicroPython con bloques.

[![License: Non-Commercial](https://img.shields.io/badge/License-Non_Commercial-red.svg)](#licencia)
### TECNOLOGÍA CON SENTIDO: Diseño de un sistema que permite el aprendizaje de programación por bloques para personas con deficiencia visual.

Aplicación de escritorio diseñada para que personas ciegas o con baja visión programen la placa BBC Micro:bit sin necesidad de ver una pantalla. Los bloques de código se representan como bloques físicos con pegatinas braille y códigos QR: la cámara los detecta, y el programa los traduce automáticamente a código MicroPython funcional a través de un autómata de pila, con lectura por voz en caso de necesitar variables.

_Desarrollado en colaboración con la ONCE (Organización Nacionad de Ciegos Españoles)._

**En el repositorio hay varias carpetas la que tiene el proyecto principal es QrReader.**

La carpeta de BrailleReader fue un intento de visión artificial usando lenguaje braille en alto contraste para la generación del código. Fue descartado por la dificultad de la detección de algunas letras. En caso de que alguien quiera desarrollarlo más se podría usar cuadrados en las esquinas estilo Qr para una lectura más simplificada.

Y por último la carpeta QrReader.old fue la primera versión semi-funcional de la aplicación sin uso de elementos importantes como el autómata de pila o el control por voz.
### Qué hace

- **Lectura de bloques por cámara**: coloca los bloques en el orden deseado, la app detecta la disposición física a través de visión artificial y genera el código MicroPython correspondiente usando una autómata de pila.
- **Control por voz**: todas las acciones (capturar, enviar a la placa, explicar el código, leer en voz alta, repasar) se pueden ejecutar por voz, transcrita localmente con Whisper.
- **Lectura de resultados**: la placa puede enviar valores por voz al ordenador mientras el programa corre, leídos en voz alta.
- **Explicación del código con IA**: en un lenguaje sencillo y sin jerga técnica, usando Gemini si hay conexión, una IA local (Ollama + phi3) si no la hay, o una lectura literal del código como último recurso.
- **Envío directo a la placa**: el código generado se sube al Micro:bit por USB con un solo comando de voz.
- **Generador de QRs**: crea e imprime en PDF los QRs de cualquier bloque del diccionario, en el tamaño que se necesite para poderlos usar en bloques físicos.
- **Editor de diccionario**: añade, edita o borra bloques disponibles sin tocar código.
- **Bilingüe** (español / inglés), con voces y caché de audio propias para cada idioma.
- **Modo alto contraste** para baja visión.

### Descargar

La aplicación no necesita instalación: se descarga, se descomprime, y se ejecuta.

Los portables para Windows, Linux y Mac están en la [sección de Releases](https://github.com/Jorbis21/TFM_MISEA/releases/) del repositorio. Cada sistema operativo tiene dos archivos:

- `MicroPython_with_blocks-<so>.zip` — la aplicación en sí, con el motor de IA local (Ollama) ya incluido.
- `MicroPython_with_blocks-<so>-phi3-model.zip` — el modelo de IA local (phi3), aparte porque supera el límite de tamaño de un único archivo de GitHub.

Para tener IA local funcionando desde el primer arranque, descomprime los dos zips primero el de la aplicación y después el modelo dentro de la carpeta de la aplicación. Si solo te interesa la explicación por Gemini (con conexión a internet) o la lectura literal del código, con el primer zip basta, pero es necesario un .env en la carpeta.

### Explicación por IA en la nube

Para usar Gemini como explicación por IA, crea un archivo `.env` junto al ejecutable con:

```
GEMINI_API_KEY=tu_clave_aqui
```

Para obtener esta clave debes meterte en [Google AI Studio](https://aistudio.google.com/), desde aquí generar tu propia clave. Sin este archivo, la app funciona igual, pasando directamente a la IA local o a la lectura literal.

### Ejecutar desde el código fuente

Requiere Python 3.12 o superior.

```
pip install -r requirements.txt
python src/main.py
```

También requiere tener ollama instalado con el modelo phi3 además de el .env al lado del main.p
### Estructura del proyecto

El proyecto sigue una arquitectura MVC:

```
src/
├── controllers/   # Orquestan modelos y vistas, sin tocar la interfaz directamente
├── models/        # Lógica de negocio: visión, traductor, voz, IA, serie...
├── views/         # Interfaz (PyQt6)
├── services/      # Servicios transversales (audio)
└── utils/         # Utilidades compartidas: idioma, constantes, rutas...
```

## Licencia

Este proyecto está bajo la licencia **PolyForm Noncommercial License 1.0.0**.

**Lo que SÍ puedes hacer:**
* Usar, modificar y distribuir este código para proyectos personales.
* Usarlo con fines educativos o de investigación.
* Usarlo en organizaciones sin ánimo de lucro.

**Lo que NO puedes hacer:**
* Usar este código (o versiones modificadas) en productos comerciales.
* Venderlo u ofrecerlo como parte de un servicio de pago.
* Usarlo en el entorno interno de una empresa con fines de lucro.

Si estás interesado en utilizar este software para fines comerciales, por favor contáctame en **[javierorbis@gmail.com]** para negociar una licencia comercial. 

Puedes leer el texto legal completo en el archivo [LICENSE](https://github.com/Jorbis21/TFM_MISEA/blob/main/LICENSE) de este repositorio.
