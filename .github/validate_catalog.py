#!/usr/bin/env python3
"""Проверка каталога blg.app: валидность JSON и правила публикации.

Запускается на каждый push и pull request. Только стандартная библиотека.
"""
import json
import sys
from datetime import datetime, timezone

ERRORS = []


def err(file, msg):
    ERRORS.append((file, msg))
    print(f"::error file={file}::{msg}")


def load(file):
    try:
        with open(file, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:  # битый JSON, нет файла и т.п.
        err(file, f"не удалось прочитать JSON: {e}")
        return None
    if not isinstance(data, list):
        err(file, "верхний уровень должен быть списком [ ... ]")
        return None
    return data


def is_http(v):
    return isinstance(v, str) and v.startswith(("http://", "https://"))


def parse_date(raw):
    try:
        d = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None
    return d if d.tzinfo else None  # без часового пояса считаем ошибкой


def check_releases():
    f = "releases.json"
    data = load(f)
    if data is None:
        return
    now = datetime.now(timezone.utc)
    album_ids, track_ids = set(), set()

    for i, a in enumerate(data):
        if not isinstance(a, dict):
            err(f, f"элемент №{i + 1}: ожидался объект")
            continue
        aid = a.get("id")
        name = f'«{a.get("title", "?")}» ({aid})'

        for key in ("id", "title", "artist", "release_date", "type", "tracks"):
            if a.get(key) in (None, ""):
                err(f, f"{name}: нет поля {key}")

        if aid in album_ids:
            err(f, f"{name}: повторяется id альбома")
        album_ids.add(aid)

        if a.get("type") not in ("release", "snippet", "unreleased"):
            err(f, f'{name}: type должен быть release, snippet или unreleased, сейчас {a.get("type")!r}')

        date = parse_date(a.get("release_date"))
        if date is None:
            err(f, f"{name}: release_date должна быть в формате 2027-01-01T00:00:00+03:00 (с часовым поясом)")

        for key in ("cover_thumb", "cover_full"):
            if a.get(key) is not None and not is_http(a.get(key)):
                err(f, f"{name}: {key} должна быть ссылкой http(s)")

        tracks = a.get("tracks")
        if not isinstance(tracks, list):
            continue
        for t in tracks:
            if not isinstance(t, dict):
                err(f, f"{name}: трек должен быть объектом")
                continue
            tid = t.get("track_id")
            tname = f'{name} / «{t.get("title", "?")}» ({tid})'
            for key in ("track_id", "title"):
                if t.get(key) in (None, ""):
                    err(f, f"{tname}: нет поля {key}")
            if tid in track_ids:
                err(f, f"{tname}: повторяется track_id")
            track_ids.add(tid)

            audio = t.get("audio_url")
            if audio not in (None, "") and not is_http(audio):
                err(f, f"{tname}: audio_url должна быть ссылкой http(s)")

            ttml = t.get("ttml_url")
            # 'assets/...' — файл, встроенный в приложение (используется в демо)
            if ttml is not None and not (is_http(ttml) or str(ttml).startswith("assets/")):
                err(f, f"{tname}: ttml_url должна быть ссылкой http(s) или null")

            # Защита от утечки: до релиза ссылки на аудио в публичном каталоге нет.
            if date is not None and date > now and audio not in (None, ""):
                err(f, f"{tname}: релиз выйдет {a.get('release_date')}, "
                       "но audio_url уже есть. Уберите его до момента дропа")


def check_artists():
    f = "artists.json"
    data = load(f)
    if data is None:
        return
    seen = set()
    for i, a in enumerate(data):
        if not isinstance(a, dict) or not a.get("name"):
            err(f, f"элемент №{i + 1}: нужен объект с полем name")
            continue
        key = a["name"].strip().lower()
        if key in seen:
            err(f, f'повторяется артист «{a["name"]}»')
        seen.add(key)
        for k in ("photo", "donate_url"):
            if a.get(k) is not None and not is_http(a.get(k)):
                err(f, f'«{a["name"]}»: {k} должна быть ссылкой http(s) или null')
        socials = a.get("socials") or {}
        if not isinstance(socials, dict):
            err(f, f'«{a["name"]}»: socials должен быть объектом')
        else:
            for k, v in socials.items():
                if not is_http(v):
                    err(f, f'«{a["name"]}»: соцсеть {k} должна быть ссылкой http(s)')


check_releases()
check_artists()

if ERRORS:
    print(f"\nНайдено проблем: {len(ERRORS)}")
    sys.exit(1)
print("Каталог в порядке.")
