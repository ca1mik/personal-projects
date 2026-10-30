"""Привязка сборки к одному компьютеру (node-lock).

Актуально только для портативной сборки (флешка), которую отдают заказчику:
без привязки один купленный экземпляр можно скопировать на сколько угодно
компьютеров. Обычная разработка и docker-прод эту проверку не видят вообще —
она включается явно, флагом `LICENSE_LOCK_ENABLED=true` в `.env` (портативная
сборка ставит его сама, см. `scripts/build-portable.ps1`).

Как это работает — офлайн, без сервера активации: у заказчика на объекте
может вообще не быть интернета, значит проверка обязана уметь работать без
него.

  1. «Отпечаток» этого компьютера — хэш от Windows ``MachineGuid`` (реестр,
     ``HKLM\\SOFTWARE\\Microsoft\\Cryptography``, читается без прав
     администратора и не переезжает вместе с папкой — это буквально то, чем
     сама Windows отличает один компьютер от другого) и серийного номера
     системного диска.
  2. Лицензия — маленький подписанный файл ``license.key`` рядом с ``.env``:
     ``{fingerprint, issued_to, issued_at, expires_at?, signature}``.
     Подписывается офлайн приватным ключом Ed25519, который остаётся ТОЛЬКО у
     разработчика (папка ``licensing/`` в корне репозитория — она не входит ни
     в один build, см. ``licensing/README.md``). В саму сборку попадает только
     публичный ключ ниже — им можно ПРОВЕРИТЬ подпись, но не подделать новую.
  3. При старте сервер проверяет: файл существует → подпись верна → отпечаток
     в файле совпадает с отпечатком этой машины → срок (если задан) не истёк.
     Не сошлось — сервер печатает текущий отпечаток компьютера и не
     поднимается вообще (см. вызов в ``app/main.py``).

Честно об ограничениях: это НЕ защита от разбора кода. Backend — обычный
Python-пакет на диске заказчика, ``license.py`` можно открыть текстовым
редактором и вырезать вызов проверки, имея доступ к файлам. Это защита от
случайного и не особо технического «поставили и на второй комп тоже» —
реалистичная угроза для клиента этого масштаба, а не от целенаправленного
взлома опытным разработчиком.
"""

from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# Публичный ключ разработчика (32 сырых байта Ed25519, base64). Им
# ПРОВЕРЯЕТСЯ подпись лицензии — подделать лицензию этим ключом нельзя, для
# этого нужен приватный ключ, который сюда никогда не попадает. Сгенерирован
# один раз `licensing/keygen.py` и вклеен сюда вручную после генерации.
#
# Пока ключ не заменён на настоящий — любая проверка лицензии гарантированно
# провалится (что и требуется: без ключа продавать лицензии некому).
PUBLIC_KEY_B64 = "MZfOXCpg2gXrwmMSKWNrOQQ1sUeVDFlWnjB/ISI+MK8="


@dataclass(frozen=True)
class LicenseCheck:
    ok: bool
    reason: str | None = None
    fingerprint: str = ""


def _machine_guid() -> str:
    """Windows MachineGuid. Модуль ``winreg`` есть только на Windows — импорт
    внутри функции, а не наверху файла: иначе backend отказывался бы
    импортироваться на Linux (docker-прод, CI), даже когда привязка
    выключена флагом и эта функция вообще не вызывается."""
    import winreg

    try:
        # Этот конкретный ключ Microsoft явно исключила из редиректа WOW64 —
        # 32- и 64-битный процесс видят один и тот же MachineGuid, отдельно
        # разбирать разрядность не нужно.
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return str(value)
    except OSError:
        return ""


def _system_volume_serial() -> str:
    """Серийный номер диска, на котором стоит Windows — не диска, откуда
    запущена сборка (флешка может быть любой буквой)."""
    system_drive = os.environ.get("SystemDrive", "C:") + "\\"
    try:
        serial = ctypes.c_uint32()
        ok = ctypes.windll.kernel32.GetVolumeInformationW(  # type: ignore[attr-defined]
            ctypes.c_wchar_p(system_drive),
            None,
            0,
            ctypes.byref(serial),
            None,
            None,
            None,
            0,
        )
        return f"{serial.value:08X}" if ok else ""
    except OSError:
        return ""


def machine_fingerprint() -> str:
    """Отпечаток этого компьютера.

    Устойчив к переносу папки сборки (флешка, другой диск, другой путь) — не
    устойчив к переустановке Windows или замене системного диска: это и
    правильно, «тот же компьютер» для лицензии значит именно это.
    """
    raw = f"{_machine_guid()}|{_system_volume_serial()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()[:32]
    # Группами по 4 символа — такую строку легче продиктовать по телефону или
    # сверить на глаз, чем сплошные 32 символа подряд.
    return "-".join(digest[i : i + 4] for i in range(0, len(digest), 4))


def _canonical_body(payload: dict) -> bytes:
    body = {key: value for key, value in payload.items() if key != "signature"}
    return json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")


def _verify_signature(payload: dict) -> bool:
    signature_b64 = payload.get("signature")
    if not signature_b64 or not isinstance(signature_b64, str):
        return False
    try:
        public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(PUBLIC_KEY_B64))
        public_key.verify(base64.b64decode(signature_b64), _canonical_body(payload))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def check_license(license_path: Path) -> LicenseCheck:
    """Проверяет лицензию для ЭТОГО компьютера. Ничего не пишет и не лечит —
    только отвечает, можно ли стартовать, и почему нет, если нельзя."""
    fingerprint = machine_fingerprint()

    if not license_path.exists():
        return LicenseCheck(False, "Файл лицензии не найден", fingerprint)

    try:
        payload = json.loads(license_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return LicenseCheck(False, "Файл лицензии повреждён", fingerprint)

    if not isinstance(payload, dict) or not _verify_signature(payload):
        return LicenseCheck(False, "Подпись лицензии неверна", fingerprint)

    if payload.get("fingerprint") != fingerprint:
        return LicenseCheck(False, "Лицензия выдана для другого компьютера", fingerprint)

    expires_at = payload.get("expires_at")
    if expires_at:
        try:
            if date.fromisoformat(expires_at) < datetime.now(UTC).date():
                return LicenseCheck(False, "Срок действия лицензии истёк", fingerprint)
        except (TypeError, ValueError):
            return LicenseCheck(False, "Файл лицензии повреждён", fingerprint)

    return LicenseCheck(True, fingerprint=fingerprint)


def enforce_or_exit(license_path: Path) -> None:
    """Вызывается из ``app/main.py`` до создания FastAPI-приложения. Не
    прошло — печатает понятную причину и отпечаток машины (его и присылают
    разработчику для новой лицензии) и завершает процесс: сервер не должен
    подниматься даже частично."""
    result = check_license(license_path)
    if result.ok:
        return

    print("=" * 60)
    print("  Fasad Production Platform — лицензия")
    print("=" * 60)
    print(f"  [!] {result.reason}")
    print()
    print(f"  Отпечаток этого компьютера: {result.fingerprint}")
    print("  Отправьте этот код разработчику, чтобы получить license.key")
    print(f"  для этой машины, и положите файл сюда: {license_path}")
    print("=" * 60)
    sys.exit(1)
