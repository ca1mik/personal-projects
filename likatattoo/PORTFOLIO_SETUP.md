# PORTFOLIO_SETUP.md

## Откуда брали файлы

- Локальная папка Яндекс.Диска:
  - `F:\Yandex.Disk\ppdstr`

## Какой способ выбран

- Выбран надежный локальный sync, а не онлайн-подключение Яндекс.Диска.
- Причина:
  - проще поддерживать
  - нет токенов на frontend
  - нет зависимости сайта от состояния API Яндекс.Диска
  - можно отбирать только сильные кадры, а не тащить всю папку подряд

## Как теперь работает синхронизация

- База портфолио по-прежнему хранится в:
  - `site/data/portfolio-library.json`
- Но новые фото больше не нужно каждый раз вручную прописывать в JSON.
- Скрипт `site/scripts/sync_portfolio.py` теперь:
  - берет уже описанные вручную карточки как приоритетные;
  - ищет новые изображения в `F:\Yandex.Disk\ppdstr`;
  - автоматически добавляет новые фото в библиотеку, если они еще не описаны;
  - пересобирает `site/data/portfolio.json`;
  - заново раскладывает optimized / thumbs / originals.

Важно:

- авто-добавление по умолчанию пропускает сырые `IMG_*.JPG` из общей папки, потому что там часто лежат процесс, студия и служебные кадры;
- фото вида `photo_*.jpg` и длинные файловые имена с работами подхватываются автоматически;
- если работу нужно вывести в самый верх или подписать красиво, ее все равно лучше зафиксировать вручную в `site/data/portfolio-library.json`.

## Куда кладутся фото в проекте

- Исходные отобранные изображения после sync:
  - `site/images/portfolio/originals/`
- Оптимизированные webp для карточек:
  - `site/images/portfolio/lettering/`
  - `site/images/portfolio/minimal/`
  - `site/images/portfolio/graphic/`
  - `site/images/portfolio/color/`
  - `site/images/portfolio/characters/`
  - `site/images/portfolio/healed/`
  - `site/images/portfolio/sketches/`
- Превью:
  - `site/images/portfolio/thumbs/`
- Фото процесса:
  - `site/images/process/`
- Фото мастера:
  - `site/images/master/`
- Фото студии:
  - `site/images/studio/`
- Фото/скрины отзывов:
  - `site/images/reviews/`

## URL на сайте

- Карточки работ:
  - `/images/portfolio/<category>/<file>.webp`
- Превью:
  - `/images/portfolio/thumbs/<file>.jpg`
- Процесс:
  - `/images/process/<file>.webp`
- Мастер:
  - `/images/master/<file>.webp`
- Студия:
  - `/images/studio/<file>.webp`

## Файл данных портфолио

- Ручная библиотека:
  - `site/data/portfolio-library.json`
- Сгенерированный публичный манифест:
  - `site/data/portfolio.json`

## Категории

- `lettering`
- `minimal`
- `graphic`
- `color`
- `characters`
- `healed`
- `sketches`
- `process`

## Текущая оптимизация изображений

Скрипт `site/scripts/sync_portfolio.py` делает:

- optimized image:
  - формат: `WEBP`
  - максимум: `1800x1800`
  - quality: `84`
- thumbnail:
  - формат: `JPG`
  - максимум: `900x900`
  - quality: `82`

## Именование файлов

- Для карточек сайта используется чистый `id`:
  - `graphic-back-01`
  - `minimal-arm-01`
  - `character-arm-01`
  - `lettering-leg-01`
  - `color-shoulder-01`
- Рекомендуемый формат:
  - только латиница
  - без пробелов
  - `<category>-<place>-<number>.jpg`

## Как добавить новую работу

### Быстрый путь — автодобавление

1. Положить фото в `F:\Yandex.Disk\ppdstr`
2. Запустить:
   - `python site/scripts/sync_portfolio.py --source "F:\Yandex.Disk\ppdstr"`
3. Скрипт сам добавит новую карточку в `site/data/portfolio-library.json`
4. Проверить:
   - `site/data/portfolio.json`
   - главную страницу
   - `/works`
   - модальное окно
5. Если карточку нужно сделать красивее — вручную поправить у нее:
   - `title`
   - `size`
   - `place`
   - `price`
   - `description`
   - `tags`
   - `featured`
6. При необходимости пересобрать хостинг-бандл:
   - `python site/scripts/build_reg_ru_bundle.py`

### Точный путь — ручная приоритизация

Если работа должна быть в hero или в начале сетки:

1. Открыть `site/data/portfolio-library.json`
2. Найти авто-добавленную карточку по `source_name`
3. Переименовать:
   - `id`
   - `title`
   - `alt`
4. Заполнить нормальные:
   - `size`
   - `place`
   - `price`
   - `description`
   - `tags`
5. Если работа должна быть в первых карточках:
   - переместить ее выше в массиве `items`
6. Если работа должна быть в первом экране:
   - добавить ее `id` в `supporting.hero`

## Как добавлять фото процесса / студии / мастера

- Для процесса:
  - `collection: "process"`
- Для студии:
  - `collection: "studio"`
- Для фото мастера:
  - `collection: "master"`

Файлы все равно описываются через `site/data/portfolio-library.json`, а скрипт сам раскладывает их по нужным папкам.

## Что сейчас уже добавлено

- 2 вручную закрепленные сильные новые работы выведены в hero и верх портфолио:
  - `graphic-forearm-dragon-01`
  - `graphic-leg-bird-01`
- автодобавление новых фото из локальной папки
- восстановлены process-видео для сайта:
  - `site/images/process/session-long-01.mov`
  - `site/images/process/prep-process-01.mov`
- из них:
  - работы
  - фото процесса
  - фото подготовленного рабочего места

## Постоянный режим синхронизации

- Для постоянного слежения за папкой добавлен watcher:
  - `site/scripts/watch_portfolio_sync.py`
- Он отслеживает новые фото и при изменениях автоматически:
  - запускает `sync_portfolio.py`
  - при желании пересобирает hosting bundle

Команда:

- `python site/scripts/watch_portfolio_sync.py --source "F:\Yandex.Disk\ppdstr" --build-bundle`

Удобный запуск:

- `run_portfolio_sync_watch.cmd`

## Что еще нужно от владельца

- отдельное сильное фото мастера крупным планом
- больше заживших работ
- 2–4 чистых карточки для надписей и минимализма
- 2–3 кадра стерильной подготовки
- скриншоты отзывов
- видео/таймлапсы можно подключать отдельным блоком позже, но не в основной сетке портфолио

## Update 2026-06-06 - HEIC и автосинхронизация

- `site/scripts/sync_portfolio.py` теперь принимает:
  - `.jpg`
  - `.jpeg`
  - `.png`
  - `.webp`
  - `.heic`
  - `.heif`
- Это позволяет просто кидать новые айфоновские фото в:
  - `F:\Yandex.Disk\ppdstr`
- После команды:
  - `python site/scripts/sync_portfolio.py --source "F:\Yandex.Disk\ppdstr"`
- Скрипт сам пересобирает:
  - optimized `.webp`
  - thumbnails `.jpg`
  - `site/data/portfolio.json`
- Для `.heic / .heif` он использует локальный `ffmpeg`, поэтому на рабочем компьютере он должен оставаться установленным.

## Update 2026-06-06 - текущий портрет мастера

- В trust-блок сейчас подключен отдельный портрет мастера:
  - source: `IMG_0963.heic`
  - public path: `/images/master/master-portrait-01.webp`
- Если нужно заменить кадр:
  1. положить новый портрет в `F:\Yandex.Disk\ppdstr`
  2. добавить или поправить карточку с `collection: "master"` в `site/data/portfolio-library.json`
  3. обновить `supporting.master`
  4. снова запустить sync

## Update 2026-06-06 - process-видео тоже синхронизируются

- В `site/data/portfolio-library.json` теперь есть блок:
  - `media_sync.process_videos`
- Он автоматически обновляет на сайте закрепленные ролики:
  - `/images/process/session-long-01.mov`
  - `/images/process/prep-process-01.mov`
- Watcher `site/scripts/watch_portfolio_sync.py` теперь следит и за видеофайлами тоже, а не только за изображениями.

## Update 2026-06-06 - visual portfolio polish

- Home portfolio now promotes featured works first.
- `object_position` in `site/data/portfolio-library.json` can be used to fine-tune crop focus per image.
- If a card crops badly, add or edit `object_position`, for example: `"object_position": "center 32%"`.
