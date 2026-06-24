import google.generativeai as genai

# Sustituye por tu clave real (suele empezar por AIza...)
genai.configure(api_key="AQ.Ab8RN6JQTC-SYK-S--HwCZ1vUbUvZ6-z-Frek--H-vkNUdFJ-w")

print("Conectando con los servidores de Google...\n")
try:
    print("Modelos compatibles y disponibles para tu clave:")
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f" -> {m.name}")
except Exception as e:
    print(f"Error de conexión: {e}")