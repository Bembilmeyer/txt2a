audiobook_converter/
├── books/                    # Сюда кидаешь исходные книги (epub, fb2, txt)
├── output/                   # Готовые аудиокниги (M4B/MP3)
├── temp/                     # Временные WAV-файлы глав
├── models/                   # Модель Silero (скачивается автоматически)
├── src/
│   ├── __init__.py
│   ├── text_extractor.py     # Извлечение текста из книг
│   ├── text_processor.py     # Очистка и сегментация текста
│   ├── silero_tts.py         # Синтез речи (Silero)
│   ├── audio_postprocess.py  # Склейка, нормализация, метаданные
│   └── main.py               # Главный скрипт запуска
├── config.yaml               # Настройки (голос, скорость, качество)
├── requirements.txt
└── README.md