"""
Синтез речи с помощью Silero TTS
"""
import torch
import torchaudio
from pathlib import Path
from typing import Optional
import yaml


class SileroTTS:
    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        self.device = torch.device('cpu')
        self.model = None
        self.sample_rate = self.config['tts']['sample_rate']
        self.voice = self.config['tts']['voice']
        self.speed = self.config['tts']['speed']

        self._load_model()

    def _load_model(self):
        """Загрузка модели Silero"""
        model_path = Path("models/v5_5_ru.pt")

        if not model_path.exists():
            print("Скачиваю модель Silero...")
            torch.hub.download_url_to_file(
                'https://models.silero.ai/models/tts/ru/v5_5_ru.pt',
                str(model_path)
            )

        importer = torch.package.PackageImporter(str(model_path))
        self.model = importer.load_pickle("tts_models", "model").to(self.device)
        print(f"Модель загружена. Голос: {self.voice}")

    def synthesize(self, text: str, output_path: Path) -> bool:
        """Синтезирует текст в WAV"""
        try:
            with torch.no_grad():
                audio = self.model.apply_tts(
                    text=text,
                    speaker=self.voice,
                    sample_rate=self.sample_rate,
                    put_accent=True,
                    put_yo=True
                )

            torchaudio.save(
                str(output_path),
                audio.unsqueeze(0),
                self.sample_rate
            )
            return True
        except Exception as e:
            print(f"Ошибка синтеза: {e}")
            return False