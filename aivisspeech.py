from voicevox import voicevox

class aivisspeech(voicevox):
    def __init__(self, text: str, speaker: int, pitch: int, speed: float):
        super().__init__(text, speaker, pitch, speed)
        self.url = self.config['aivisspeech']['url']
        self.params = {
            'text': text,
            'speaker': speaker
        }

    async def get_audio(self) -> bytes:
        try:
            return await self._get_engine()
        except Exception as e:
            raise RuntimeError(e)
