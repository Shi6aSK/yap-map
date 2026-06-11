import asyncio
from app.services.transcription.vosk_transcriber import VoskTranscriber
from app.services.local_models import LocalModelManager

def main():
    mm = LocalModelManager()
    print('manifest:', mm.manifest)
    path = mm.manifest.get('vosk_model')
    print('vosk path:', path)
    if not path:
        print('No vosk model found in manifest')
        return
    t = VoskTranscriber(model_path=path)
    asyncio.run(t.start())
    print('Vosk model loaded OK')

if __name__ == '__main__':
    main()
