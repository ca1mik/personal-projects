# video-auto-cutter

Локальный инструмент для автоматической нарезки длинных видео с Яндекс.Диска в короткие вертикальные ролики под `Reels / Shorts / TikTok`, с отдельной специализацией под тату-контент.

Проект умеет:

- скачивать видео по публичной ссылке Яндекс.Диска или из `links.txt`
- автоматически находить небольшие пригодные к обработке видеофайлы
- делать `Talking Reels`, если в видео есть речь
- делать `tattoo process`, `close-up`, `satisfying`, `portfolio`, `before/process/after`
- собирать `timelapse clean` и `timelapse overlay`
- делать `stories` 5–15 секунд
- генерировать субтитры, overlay-тексты, caption и hashtags
- складывать лучшие ролики в `output/best`
- сохранять отчёты в `output/reports`

## Для кого

- тату-мастер
- рилсмейкер для тату-аккаунта
- студия, которая снимает процесс сеансов
- личный бренд мастера

## Структура

```text
video-auto-cutter/
  run.py
  install.py
  config.yaml
  links.txt
  input/
  downloads/
  output/
    best/
    talking/
    tattoo_process/
    closeups/
    satisfying/
    before_after/
    portfolio/
    timelapse/
    stories/
    previews/
    thumbnails/
    transcripts/
    subtitles/
    captions/
    metadata/
    reports/
    rejected/
  processed/
  logs/
```

## Установка Python

Проверь:

```bash
python --version
```

Нужен Python `3.10+`.

## Установка FFmpeg

Windows:

```powershell
winget install Gyan.FFmpeg
```

macOS:

```bash
brew install ffmpeg
```

Ubuntu / Debian:

```bash
sudo apt update
sudo apt install ffmpeg
```

Проверка:

```bash
ffmpeg -version
ffprobe -version
```

## Установка проекта

```bash
python install.py
```

`install.py`:

- проверяет Python `3.10+`
- проверяет `ffmpeg` и `ffprobe`
- ставит зависимости
- создаёт папки проекта
- создаёт `.env` из `.env.example`

## Яндекс.Диск

Видео сначала скачиваются в:

```text
downloads/
```

Временные файлы:

```text
downloads/tmp/
```

Неудачные скачивания:

```text
downloads/failed/
```

Manifest скачиваний:

```text
downloads/download_manifest.json
```

В `links.txt` уже лежит ссылка:

```text
https://disk.yandex.ru/d/T-qGlSvi7Pm_uA
```

## Базовые команды

```bash
python run.py
python run.py --dry-run
python run.py --install-check
python run.py --analyze-only
python run.py --download-only --yadisk-url "https://disk.yandex.ru/d/T-qGlSvi7Pm_uA"
python run.py --links links.txt
python run.py --strategy aggressive
python run.py --strategy balanced
python run.py --strategy expert
```

## Режимы для тату-контента

```bash
python run.py --yadisk-url "https://disk.yandex.ru/d/T-qGlSvi7Pm_uA" --mode all
python run.py --yadisk-url "https://disk.yandex.ru/d/T-qGlSvi7Pm_uA" --mode tattoo
python run.py --yadisk-url "https://disk.yandex.ru/d/T-qGlSvi7Pm_uA" --mode timelapse
python run.py --mode portfolio
python run.py --mode tattoo --make-stories
```

Поведение:

- `--mode auto`: сам решает, что делать с видео
- `--mode talking`: только говорящие клипы
- `--mode tattoo`: процесс, детали, satisfying, before/after
- `--mode timelapse`: только таймлапс
- `--mode portfolio`: только чистые эстетичные клипы
- `--mode all`: всё сразу

## Где искать результат

Лучшие ролики:

```text
output/best
```

Готовые тату-клипы:

```text
output/tattoo_process
output/closeups
output/satisfying
output/before_after
output/portfolio
output/timelapse
output/stories
```

Говорящие клипы:

```text
output/talking
```

Субтитры:

```text
output/subtitles
```

Отчёты:

```text
output/reports
```

## Whisper и слабый ПК

Если Whisper не поставился или машина слабая:

```bash
python run.py --no-transcription
```

Проект не падает и продолжает делать tattoo/timelapse/portfolio/stories без транскрипта.

## Если Яндекс.Диск не скачивается

Проверь:

- ссылка точно публичная
- интернет доступен
- в `.env` есть `YADISK_TOKEN`, если ссылка приватная

## Если FFmpeg не найден

Поставь FFmpeg командой для своей ОС и снова запусти:

```bash
python run.py --install-check
```

## Практический запуск

```bash
python install.py
python run.py --install-check
python run.py --dry-run --yadisk-url "https://disk.yandex.ru/d/T-qGlSvi7Pm_uA" --mode all
python run.py --yadisk-url "https://disk.yandex.ru/d/T-qGlSvi7Pm_uA" --mode all
```
