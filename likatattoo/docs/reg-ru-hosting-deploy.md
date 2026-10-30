# REG.RU hosting deploy

## Best path for this project

- The home PC path is blocked by ISP CGNAT.
- The stable path is the already paid REG.RU shared hosting `Host-0`.
- For the public site, upload only the prepared static bundle, not the whole repo.

## What is already prepared

- Bundle builder:
  - `python site/scripts/build_reg_ru_bundle.py --domain ppdstr.ru`
- Ready upload folder after build:
  - `deploy/reg-ru/ppdstr.ru/public_html`
- Ready upload zip after build:
  - `deploy/reg-ru/ppdstr.ru-upload.zip`

## Recommended primary domain

- Use `ppdstr.ru` as the main public domain first.
- Later `ppdstr.online` can be attached as an alias or redirected to `.ru`.

## Exact DNS for REG.RU shared hosting

For `ppdstr.ru`:

- `A @ -> 31.31.197.13`
- `A www -> 31.31.197.13`

If `ppdstr.online` will use the same hosting too:

- `A @ -> 31.31.197.13`
- `A www -> 31.31.197.13`

## What to click in REG.RU

1. Open `Host-0`.
2. Click `Войти в панель`.
3. Add a site:
   - domain: `ppdstr.ru`
   - document root: `public_html`
4. Open the file manager for that site.
5. Upload the contents of `deploy/reg-ru/ppdstr.ru/public_html`
   or upload and unpack `deploy/reg-ru/ppdstr.ru-upload.zip`.
6. Enable the free SSL certificate in the hosting panel.
7. In the domain DNS zone, point `@` and `www` to `31.31.197.13`.

## What should open after deploy

- `/` -> client landing
- `/offer` -> public offer
- `/payment` -> payment and refund rules
- `/privacy` -> privacy policy

## Important note about the bot

- Shared hosting is good for the static public site.
- The Telegram bot and future Robokassa callback backend are better kept on:
  - a VPS
  - or another Python-capable public server
