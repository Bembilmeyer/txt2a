```
txt2a/
├── books/                    # Сюда кидаешь исходные книги (epub, fb2, txt)
├── output/                   # Готовые аудиокниги (M4B/MP3/WAV)
├── temp/                     # Фрагменты глав в WAV + склеенный WAV
├── models/                   # Модель Silero (~145 МБ, скачивается автоматически)
├── src/
│   ├── text_extractor.py     # Книга -> список глав (EPUB/FB2/TXT)
│   ├── text_processor.py     # Очистка и разбиение на фрагменты с паузами
│   ├── silero_tts.py         # Синтез речи (Silero), запись WAV
│   ├── audio_postprocess.py  # Потоковая склейка + кодирование через ffmpeg
│   └── main.py               # Главный скрипт запуска
├── config.yaml               # Настройки (голос, скорость, формат, качество)
├── requirements.txt
├── CLAUDE.md                 # Архитектура и подводные камни (для Claude Code)
└── README.md
```

Содержимое `books/`, `output/`, `temp/` и `models/` не хранится в git — см. `.gitignore`.
Описание архитектуры и неочевидных мест — в `CLAUDE.md`.
