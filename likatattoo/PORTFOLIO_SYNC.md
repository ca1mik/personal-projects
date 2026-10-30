# PORTFOLIO_SYNC.md

## Где сейчас лежат работы
- Локальный путь пользователя:
  - `F:\Yandex.Disk\ppdstr`

## Куда класть работы в проекте
- Путь:
  - originals: `site/images/portfolio/originals/`
  - optimized: `site/images/portfolio/optimized/`
  - thumbnails: `site/images/portfolio/thumbnails/`
  - manifest: `site/data/portfolio.json`
  - зеркало для бота: `assets/portfolio/fresh/`
- URL на сайте:
  - `/images/portfolio/optimized/<file>.webp`
  - `/images/portfolio/thumbnails/<file>.jpg`
  - `/images/portfolio/originals/<file>.jpg`
- Форматы:
  - вход: `.jpg`, `.jpeg`, `.png`, `.webp`
  - выход:
    - optimized: `webp`
    - thumbnails: `jpg`
- Рекомендуемый размер:
  - исходник до `3000 px` по большей стороне
  - оптимизированный файл около `1600 px`
  - превью около `720 px`
- Правила именования файлов:
  - можно класть в исходную папку любые названия
  - при sync они будут slugified автоматически
  - для ручной категоризации лучше использовать подпапки:
    - `F:\Yandex.Disk\ppdstr\fresh`
    - `F:\Yandex.Disk\ppdstr\lettering`
    - `F:\Yandex.Disk\ppdstr\minimalism`
    - `F:\Yandex.Disk\ppdstr\graphics`
    - `F:\Yandex.Disk\ppdstr\color`
    - `F:\Yandex.Disk\ppdstr\healed`

## Выбранный способ
- Ручное копирование + локальный sync из папки Яндекс.Диска

## Почему выбран этот способ
- не нужны токены Яндекс.Диска
- нельзя случайно засветить API-секреты на фронтенде
- сайт не зависит от онлайна Яндекс.Диска
- изображения сразу оптимизируются под сайт
- можно безопасно деплоить готовый комплект файлов на статический хостинг

## Если sync
- реализован локальный sync-скрипт:
  - `python site/scripts/sync_portfolio.py --source "F:\Yandex.Disk\ppdstr"`
- кеширование:
  - сайт читает готовый JSON-манифест `site/data/portfolio.json`
- Fallback:
  - если sync не запускался, frontend показывает fallback-состояние галереи
- Риски:
  - видео `.mov` сейчас игнорируются
  - без подпапок все изображения попадут в категорию `fresh`

## Инструкция для пользователя
1. Положить новые изображения в `F:\Yandex.Disk\ppdstr` или в тематическую подпапку.
2. Не использовать `.mov` как единственный формат для работы в галерее; для сайта нужны фото.
3. Выполнить:
   - `python site/scripts/sync_portfolio.py --source "F:\Yandex.Disk\ppdstr"`
4. Проверить результат:
   - `site/data/portfolio.json`
   - `site/images/portfolio/optimized/`
5. Запустить smoke:
   - `python site/scripts/smoke_check.py`
