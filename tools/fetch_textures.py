# -*- coding: utf-8 -*-
"""
Загрузчик бесшовных текстур с Poly Haven (CC0).

Использование:
    python tools/fetch_textures.py

Что делает:
    1. Для каждой текстуры из TARGETS делает запрос к api.polyhaven.com
       (обязательно с User-Agent — иначе блокируется).
    2. Находит файл формата PNG / разрешения 1k / карты Diffuse.
    3. Скачивает во временную папку.
    4. Уменьшает до 512x512 (LANCZOS).
    5. Сохраняет в textures/{slug}.png и текстуру-превью 64x64
       в textures/preview/{slug}.png.

Зависимости: только requests и Pillow.
"""

import io
import json
import os
import sys
import time
import urllib.request
import urllib.error

try:
    from PIL import Image
except ImportError:
    print("Не найден Pillow. Установите: pip install Pillow")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("Не найден requests. Установите: pip install requests")
    sys.exit(1)


API_BASE = "https://api.polyhaven.com"
USER_AGENT = "CharacterGenerator/1.0 (texture fetcher)"

# Итоговые размеры
TEXTURE_SIZE = 512   # размер итоговой текстуры
PREVIEW_SIZE = 64    # размер превью для UI


# ------------------------------------------------------------------
# Целевые текстуры. slug — имя файла у нас; ph_id — ID в Poly Haven.
# Если ID в Poly Haven не найдётся — в логе будет предупреждение,
# и скрипт продолжит работу с остальными.
# ------------------------------------------------------------------
TARGETS = [
    {"slug": "metal_brushed", "ph_id": "brushed_metal_02",     "name": "Brushed Metal"},
    {"slug": "metal_gold",    "ph_id": "gold_ore",             "name": "Gold Ore"},
    {"slug": "wood_oak",      "ph_id": "oak_veneer_01",        "name": "Oak Wood"},
    {"slug": "stone_marble",  "ph_id": "marble_01",            "name": "Marble"},
    {"slug": "stone_granite", "ph_id": "granite_speckled",     "name": "Granite"},
    {"slug": "paper_aged",    "ph_id": "paper_001",            "name": "Paper"},
    {"slug": "leather_brown", "ph_id": "leather_brown_02",     "name": "Leather Brown"},
    {"slug": "fabric_linen",  "ph_id": "linen_fabric",         "name": "Linen Fabric"},
    {"slug": "water_ripple",  "ph_id": "water_ripples_01",     "name": "Water Ripples"},
    {"slug": "fire_plasma",   "ph_id": "lava_01",              "name": "Lava"},
]


# ==================================================================
#  HTTP helpers
# ==================================================================

def _get_json(url):
    """GET JSON с нашим User-Agent. Возвращает dict или None."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        return json.loads(data.decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {url}")
        return None
    except Exception as e:
        print(f"  Ошибка запроса {url}: {e}")
        return None


def _find_best_url(files_json, resolution="1k", mime_part="png", map_key="Diffuse"):
    """
    Ищет в JSON от /files/{id} ссылку на нужный файл.

    Структура ответа Poly Haven:
        {
          "Diffuse": {
            "1k": {"png": {"url": "...", "size": ..., "md5": ...}},
            "2k": {...},
            ...
          },
          "Roughness": {...},
          ...
        }
    """
    if not isinstance(files_json, dict):
        return None

    # Ищем карту (Diffuse обычно есть; иногда называется "diffuse", "col", "albedo")
    candidates = [map_key, "diffuse", "col", "albedo", "Color"]
    map_block = None
    for k in candidates:
        if k in files_json:
            map_block = files_json[k]
            break
    if map_block is None:
        # На всякий случай — если карт нет, попробуем первую доступную
        for k, v in files_json.items():
            if isinstance(v, dict):
                map_block = v
                print(f"  карты '{map_key}' нет, беру '{k}'")
                break
    if not isinstance(map_block, dict):
        return None

    # Разрешение
    res_block = map_block.get(resolution) or map_block.get("2k") or map_block.get("4k")
    if not isinstance(res_block, dict):
        return None

    # Формат
    fmt_block = res_block.get(mime_part) or res_block.get("jpg")
    if not isinstance(fmt_block, dict):
        return None

    return fmt_block.get("url")


def _download(url, timeout=60):
    """Скачивает файл и возвращает байты."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


# ==================================================================
#  Обработка одной текстуры
# ==================================================================

def process_texture(spec, out_dir, preview_dir):
    """Скачивает одну текстуру, сохраняет уменьшенную + превью."""
    slug = spec["slug"]
    ph_id = spec["ph_id"]
    out_path = os.path.join(out_dir, f"{slug}.png")
    preview_path = os.path.join(preview_dir, f"{slug}.png")

    if os.path.exists(out_path) and os.path.exists(preview_path):
        print(f"[skip] {slug} — уже есть")
        return True

    print(f"[fetch] {slug} ({ph_id})...")

    # 1. Метаданные
    files_json = _get_json(f"{API_BASE}/files/{ph_id}")
    if not files_json:
        print(f"  ✗ не удалось получить метаданные для {ph_id}")
        return False

    # 2. URL на 1k PNG Diffuse
    url = _find_best_url(files_json, resolution="1k", mime_part="png", map_key="Diffuse")
    if not url:
        print(f"  ✗ не нашёл подходящий файл для {ph_id}")
        return False

    # 3. Скачиваем
    try:
        raw = _download(url)
    except Exception as e:
        print(f"  ✗ ошибка скачивания: {e}")
        return False

    # 4. Открываем, приводим к RGBA (на случай grayscale/jpg), уменьшаем
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
    except Exception as e:
        print(f"  ✗ не открыть изображение: {e}")
        return False

    img_big = img.resize((TEXTURE_SIZE, TEXTURE_SIZE), Image.Resampling.LANCZOS)
    img_big.save(out_path, "PNG", optimize=True)

    img_small = img.resize((PREVIEW_SIZE, PREVIEW_SIZE), Image.Resampling.LANCZOS)
    img_small.save(preview_path, "PNG", optimize=True)

    size_kb = os.path.getsize(out_path) // 1024
    print(f"  ✓ {slug}.png ({size_kb} КБ, {TEXTURE_SIZE}×{TEXTURE_SIZE})")
    return True


# ==================================================================
#  main
# ==================================================================

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(here)
    out_dir = os.path.join(project_root, "textures")
    preview_dir = os.path.join(out_dir, "preview")

    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(preview_dir, exist_ok=True)

    ok, fail = 0, 0
    for spec in TARGETS:
        try:
            if process_texture(spec, out_dir, preview_dir):
                ok += 1
            else:
                fail += 1
        except KeyboardInterrupt:
            print("\nПрервано пользователем.")
            break
        except Exception as e:
            print(f"  ✗ ошибка обработки {spec['slug']}: {e}")
            fail += 1
        time.sleep(0.4)  # вежливость к API

    print()
    print(f"Готово. Успешно: {ok}, ошибок: {fail}.")
    print(f"Текстуры:  {out_dir}")
    print(f"Превью:    {preview_dir}")


if __name__ == "__main__":
    main()