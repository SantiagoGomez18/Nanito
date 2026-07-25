from tools.voiceTool import VoiceTool

voice = VoiceTool()
print(f"Probando microfono, index={voice.device_index}")
print("Habla ahora...")
resultado = voice.listen(show_status=True, show_errors=True)
print(f"Resultado: '{resultado}'")
