"""
Постобработка аудио: склейка, нормализация, кодирование, метаданные
"""
import shutil
import subprocess
import wave
from pathlib import Path
from typing import List, Optional, Sequence

# Кодеки и контейнеры по расширению итогового файла
_ENCODERS = {
    'mp3': ('libmp3lame', 'mp3'),
    'm4b': ('aac', 'mp4'),
    'm4a': ('aac', 'mp4'),
}


class FFmpegNotFound(RuntimeError):
    """ffmpeg отсутствует в PATH"""


def find_ffmpeg() -> Optional[str]:
    """Возвращает путь к ffmpeg или None"""
    return shutil.which('ffmpeg')


def require_ffmpeg() -> str:
    """Возвращает путь к ffmpeg либо падает с внятным объяснением"""
    ffmpeg = find_ffmpeg()
    if ffmpeg is None:
        raise FFmpegNotFound(
            "ffmpeg не найден в PATH. Установи его (winget install Gyan.FFmpeg) "
            "и перезапусти терминал, либо поставь output.format: wav в config.yaml."
        )
    return ffmpeg


def silence_frames(n_ms: int, sample_rate: int, sample_width: int = 2) -> bytes:
    """Генерирует тишину нужной длительности"""
    return b'\x00' * (int(sample_rate * n_ms / 1000) * sample_width)


def concatenate_wavs(
    wav_files: Sequence[Path],
    output_path: Path,
    pauses_ms: Optional[Sequence[int]] = None,
) -> Path:
    """
    Склеивает WAV-файлы в один, вставляя паузу после каждого.

    Пишет потоково, кадр за кадром, поэтому книга на десять часов не требует
    десяти часов аудио в оперативной памяти. Параметры (sample rate, разрядность)
    берутся из первого файла; файлы с другими параметрами пропускаются, иначе
    склейка дала бы кашу из ускоренного и замедленного звука.
    """
    if not wav_files:
        raise ValueError("Нет WAV-файлов для склейки")

    if pauses_ms is None:
        pauses_ms = [0] * len(wav_files)

    with wave.open(str(wav_files[0]), 'rb') as first:
        params = first.getparams()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    skipped = 0
    with wave.open(str(output_path), 'wb') as out:
        out.setparams(params)

        for wav_file, pause in zip(wav_files, pauses_ms):
            with wave.open(str(wav_file), 'rb') as src:
                if (src.getframerate(), src.getsampwidth(), src.getnchannels()) != (
                    params.framerate, params.sampwidth, params.nchannels
                ):
                    skipped += 1
                    continue
                out.writeframes(src.readframes(src.getnframes()))

            if pause > 0:
                out.writeframes(
                    silence_frames(pause, params.framerate, params.sampwidth)
                )

    if skipped:
        print(f"  Пропущено фрагментов с другими параметрами аудио: {skipped}")

    return output_path


def wav_duration_sec(wav_path: Path) -> float:
    """Длительность WAV в секундах"""
    with wave.open(str(wav_path), 'rb') as w:
        return w.getnframes() / w.getframerate()


def _build_filters(normalize: bool, remove_silence: bool, speed: float) -> List[str]:
    """Собирает цепочку аудиофильтров ffmpeg"""
    filters = []

    if remove_silence:
        # Схлопывает затяжные паузы внутри синтеза, не вырезая их полностью:
        # дыхание между фразами в аудиокниге нужно.
        filters.append(
            'silenceremove='
            'stop_periods=-1:stop_duration=0.7:stop_threshold=-50dB:detection=rms'
        )

    if abs(speed - 1.0) > 1e-3:
        # atempo меняет темп без искажения высоты голоса, но работает только
        # в диапазоне 0.5–2.0, поэтому раскладываем в цепочку.
        remaining = speed
        while remaining > 2.0:
            filters.append('atempo=2.0')
            remaining /= 2.0
        while remaining < 0.5:
            filters.append('atempo=0.5')
            remaining /= 0.5
        filters.append(f'atempo={remaining:.4f}')

    if normalize:
        # loudnorm (EBU R128) вместо пикового выравнивания: у синтеза громкость
        # плавает между чанками, и ровная воспринимаемая громкость важнее пика.
        # -18 LUFS — ориентир для аудиокниг.
        filters.append('loudnorm=I=-18:TP=-2.0:LRA=11')

    return filters


def _restore_sample_rate(filters: List[str], sample_rate: Optional[int]) -> List[str]:
    """Возвращает частоту дискретизации к исходной после фильтров"""
    # loudnorm внутри работает на 192 кГц и отдаёт поток с этой частотой.
    # Без явного aresample кодер округляет её до ближайшей поддерживаемой
    # (для AAC — 96 кГц) и зря кодирует апсемплированный звук: качества это
    # не добавляет, а 96 кГц поддерживают не все плееры. На размер файла не
    # влияет — его задаёт битрейт.
    if filters and sample_rate:
        filters.append(f'aresample={sample_rate}')
    return filters


def encode_audiobook(
    source_wav: Path,
    output_path: Path,
    bitrate: str = '96k',
    normalize: bool = True,
    remove_silence: bool = False,
    speed: float = 1.0,
    title: Optional[str] = None,
) -> Path:
    """Кодирует склеенный WAV в итоговый формат через ffmpeg"""
    suffix = output_path.suffix.lower().lstrip('.')
    if suffix not in _ENCODERS:
        raise ValueError(
            f"Неподдерживаемый формат вывода: {suffix}. "
            f"Доступны: {', '.join(_ENCODERS)}, wav"
        )

    codec, container = _ENCODERS[suffix]
    ffmpeg = require_ffmpeg()

    cmd = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-i', str(source_wav)]

    with wave.open(str(source_wav), 'rb') as src:
        source_rate = src.getframerate()

    filters = _restore_sample_rate(
        _build_filters(normalize, remove_silence, speed), source_rate
    )
    if filters:
        cmd += ['-af', ','.join(filters)]

    cmd += ['-c:a', codec, '-b:a', bitrate]

    if title:
        cmd += ['-metadata', f'title={title}', '-metadata', f'album={title}']
        cmd += ['-metadata', 'genre=Audiobook']

    cmd += ['-f', container, str(output_path)]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg завершился с кодом {result.returncode}:\n{result.stderr.strip()}"
        )

    return output_path
