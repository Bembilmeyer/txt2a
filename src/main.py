"""
Главный скрипт конвертации книг в аудиокниги
"""
from pathlib import Path
from tqdm import tqdm
import yaml

from text_extractor import extract_text, clean_text
from text_processor import split_into_chunks
from silero_tts import SileroTTS
from audio_postprocess import concatenate_chapters


def process_book(book_path: Path, config: dict):
    """Обрабатывает одну книгу"""
    print(f"\n=== Обработка: {book_path.name} ===")

    # 1. Извлечение текста
    raw_text = extract_text(book_path)
    text = clean_text(raw_text)

    # 2. Разбиение на чанки
    chunks = split_into_chunks(text, config['processing']['chunk_size'])
    print(f"Всего чанков: {len(chunks)}")

    # 3. Синтез
    tts = SileroTTS()
    temp_dir = Path(config['paths']['temp_dir']) / book_path.stem
    temp_dir.mkdir(parents=True, exist_ok=True)

    chapter_files = []

    for i, chunk in enumerate(tqdm(chunks, desc="Синтез")):
        output_file = temp_dir / f"chunk_{i:04d}.wav"
        if tts.synthesize(chunk, output_file):
            chapter_files.append(output_file)

    # 4. Склейка
    output_dir = Path(config['paths']['output_dir'])
    output_dir.mkdir(exist_ok=True)

    final_file = output_dir / f"{book_path.stem}.mp3"
    concatenate_chapters(chapter_files, final_file)

    print(f"Готово: {final_file}")


def main():
    with open("config.yaml", 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    books_dir = Path(config['paths']['books_dir'])

    for book in books_dir.glob("*"):
        if book.suffix.lower() in ['.epub', '.txt', '.fb2']:
            process_book(book, config)


if __name__ == "__main__":
    main()