"""
Постобработка аудио: склейка, нормализация, метаданные
"""
from pydub import AudioSegment
from pathlib import Path
import subprocess


def normalize_audio(audio: AudioSegment) -> AudioSegment:
    """Нормализация громкости"""
    return audio.normalize()


def concatenate_chapters(chapter_files: list[Path], output_path: Path):
    """Склеивает главы в одну аудиокнигу"""
    combined = AudioSegment.empty()

    for chapter in sorted(chapter_files):
        audio = AudioSegment.from_wav(str(chapter))
        combined += audio

    combined.export(str(output_path), format="mp3", bitrate="96k")
    print(f"Создана аудиокнига: {output_path}")