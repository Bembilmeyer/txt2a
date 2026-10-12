"""
Синтез речи с помощью Silero TTS
"""
import warnings
import wave
from pathlib import Path

import torch

MODEL_URL = 'https://models.silero.ai/models/tts/ru/v5_5_ru.pt'

# Silero принимает только эти частоты дискретизации
SUPPORTED_RATES = (8000, 24000, 48000)


class SileroTTS:
    def __init__(self, config: dict, model_dir: Path, device: str = 'cpu'):
        tts_config = config['tts']

        self.device = torch.device(device)
        self.model = None
        self.sample_rate = tts_config['sample_rate']
        self.voice = tts_config['voice']
        self.model_dir = Path(model_dir)

        if self.sample_rate not in SUPPORTED_RATES:
            raise ValueError(
                f"sample_rate={self.sample_rate} не поддерживается Silero. "
                f"Допустимо: {SUPPORTED_RATES}"
            )

        self._load_model()

    def _download_model(self, model_path: Path):
        """Скачивает модель во временный файл и только потом переименовывает"""
        print(f"Скачиваю модель Silero (~145 МБ): {MODEL_URL}")
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # Качаем в .part, чтобы прерванная загрузка не осталась лежать
        # под именем готовой модели и не падала потом при распаковке.
        partial = model_path.with_suffix(model_path.suffix + '.part')
        torch.hub.download_url_to_file(MODEL_URL, str(partial), progress=True)
        partial.replace(model_path)

    def _load_model(self):
        """Загрузка модели Silero"""
        model_path = self.model_dir / 'v5_5_ru.pt'

        if not model_path.exists():
            self._download_model(model_path)

        importer = torch.package.PackageImporter(str(model_path))

        # Внутри пакета Silero есть regex с устаревшим экранированием, что даёт
        # SyntaxWarning на каждом запуске. Код чужой и править его мы не можем,
        # поэтому глушим предупреждение только на время импорта.
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', SyntaxWarning)
            model = importer.load_pickle("tts_models", "model")

        # .to() у Silero-пакета, в отличие от nn.Module, не возвращает self:
        # писать model = model.to(device) нельзя — получится None.
        model.to(self.device)
        self.model = model

        speakers = getattr(self.model, 'speakers', None)
        if speakers and self.voice not in speakers:
            raise ValueError(
                f"Голос '{self.voice}' не найден в модели. "
                f"Доступны: {', '.join(speakers)}"
            )

        print(f"Модель загружена. Голос: {self.voice}, {self.sample_rate} Гц")

    def _write_wav(self, audio: torch.Tensor, output_path: Path):
        """Пишет моно-WAV 16 бит средствами стандартной библиотеки"""
        # clamp до записи: за пределами [-1, 1] int16 заворачивается
        # и вместо громкого места получается треск.
        samples = (audio.detach().cpu().clamp(-1.0, 1.0) * 32767).to(torch.int16)

        with wave.open(str(output_path), 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.sample_rate)
            w.writeframes(samples.numpy().tobytes())

    def synthesize(self, text: str, output_path: Path) -> bool:
        """Синтезирует текст в WAV. False — чанк пропущен, обработка продолжается"""
        if not text or not text.strip():
            return False

        try:
            with torch.no_grad():
                audio = self.model.apply_tts(
                    text=text,
                    speaker=self.voice,
                    sample_rate=self.sample_rate,
                    put_accent=True,
                    put_yo=True
                )

            if audio.numel() == 0:
                return False

            self._write_wav(audio, output_path)
            return True
        except Exception as e:
            preview = text[:40].replace('\n', ' ')
            print(f"\nОшибка синтеза ({len(text)} симв., '{preview}...'): {e}")
            return False
