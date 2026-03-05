import urllib.request
import json
import sys
import os
import base64
import re

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MANIFEST_URL = "https://gametora.com/data/manifests/umamusume.json"
CDN_BASE = "https://gametora.com/data/umamusume"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

NAME_KEY = 106
NAME_OFFSET = 86
REWARD_OFFSET = 36

TYPE_MAP = {
    "sp": "speed",
    "st": "stamina",
    "po": "power",
    "gu": "guts",
    "in": "wit",
}


def fetch_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def decrypt(encoded, key_num):
    if not encoded:
        return ""
    raw = base64.b64decode(encoded)
    key = f"k{key_num}".encode("utf-8")
    return bytes(
        b ^ key[i % len(key)] for i, b in enumerate(raw)
    ).decode("utf-8", errors="replace")


def fetch_cdn_data():
    manifest = fetch_json(MANIFEST_URL)

    def cdn(key):
        return fetch_json(f"{CDN_BASE}/{key}.{manifest[key]}.json")

    print("  Downloading manifest and data files...")
    return {
        "te_names": cdn("dict/te_names_en"),
        "evrew": cdn("dict/evrew"),
        "characters": cdn("characters"),
        "char_cards": cdn("character-cards"),
        "supports": cdn("support-cards"),
        "skills": cdn("skills"),
        "status_effects": cdn("status-effects"),
        "events_char": cdn("training_events/char"),
        "events_char_card": cdn("training_events/char_card"),
        "events_ssr": cdn("training_events/ssr"),
        "events_sr": cdn("training_events/sr"),
        "events_shared": cdn("training_events/shared"),
    }


_JP_RE = re.compile(r"[\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]")


def get_event_name(te_names, raw_idx):
    idx = raw_idx - NAME_OFFSET
    if 0 <= idx < len(te_names) and te_names[idx]:
        name = decrypt(te_names[idx], NAME_KEY)
        if _JP_RE.search(name):
            return ""
        return name
    return ""


def build_skill_map(skills):
    return {
        s["id"]: s.get("name_en", "")
        for s in skills
        if isinstance(s, dict) and "id" in s
    }


def build_status_effect_map(status_effects):
    return {
        se["id"]: se.get("name_en", "")
        for se in status_effects
        if isinstance(se, dict) and "id" in se
    }


def build_char_map(characters):
    return {
        c["char_id"]: c["en_name"]
        for c in characters
        if isinstance(c, dict) and "char_id" in c and "en_name" in c
    }


def build_global_char_ids(characters):
    return set(
        c["char_id"]
        for c in characters
        if isinstance(c, dict) and c.get("playable_en")
    )


def build_global_support_ids(supports):
    return set(
        s["support_id"]
        for s in supports
        if isinstance(s, dict) and s.get("release_en")
    )


def build_support_map(supports):
    result = {}
    for s in supports:
        if not isinstance(s, dict) or "support_id" not in s:
            continue
        result[s["support_id"]] = {
            "name": s.get("char_name", ""),
            "url_name": s.get("url_name", ""),
            "rarity": s.get("rarity", ""),
            "type": s.get("type", ""),
            "support_id": s["support_id"],
        }
    return result


def parse_value(val_str):
    if not val_str:
        return 0
    val_str = str(val_str).strip().lstrip("+")
    if "/" in val_str:
        parts = [p.strip().lstrip("+") for p in val_str.split("/")]
        nums = [int(p) for p in parts if p.lstrip("-").isdigit()]
        return round(sum(nums) / len(nums)) if nums else 0
    try:
        return int(val_str)
    except ValueError:
        return 0


def decode_rewards(raw_indices, evrew):
    results = []
    for raw in raw_indices:
        idx = raw - REWARD_OFFSET
        if 0 <= idx < len(evrew) and evrew[idx]:
            r = evrew[idx]
            entry = {"t": r[0]}
            if len(r) > 1:
                entry["v"] = r[1]
            if len(r) > 2:
                entry["d"] = r[2]
            results.append(entry)
    return results


def convert_results(results, skill_map, se_map):
    effects = {}
    skills = []
    conditions = []
    for r in results:
        t = r.get("t", "")
        v = r.get("v", "")
        d = r.get("d")
        if t == "di":
            break
        if t in TYPE_MAP:
            val = parse_value(v)
            if val:
                effects[TYPE_MAP[t]] = effects.get(TYPE_MAP[t], 0) + val
        elif t == "5s":
            val = parse_value(v)
            if val:
                for stat in ("speed", "stamina", "power", "guts", "wit"):
                    effects[stat] = effects.get(stat, 0) + val
        elif t == "en":
            val = parse_value(v)
            if val:
                effects["energy"] = effects.get("energy", 0) + val
        elif t == "mo":
            val = parse_value(v)
            if val:
                effects["mood"] = effects.get("mood", 0) + val
        elif t == "pt":
            val = parse_value(v)
            if val:
                effects["skill_pts"] = effects.get("skill_pts", 0) + val
        elif t == "bo":
            val = parse_value(v)
            if val:
                effects["friendship"] = effects.get("friendship", 0) + val
        elif t == "me":
            val = parse_value(v)
            if val:
                effects["max_energy"] = effects.get("max_energy", 0) + val
        elif t == "se":
            name = se_map.get(d, "")
            if name:
                conditions.append(name)
        elif t == "sk":
            level = parse_value(v) if v else 1
            name = skill_map.get(d, "")
            if name:
                skills.append({"name": name, "level": max(1, level)})
    return effects, skills, conditions


def has_diverge(results):
    return any(r.get("t") == "di" for r in results)


def split_outcomes(results):
    branches = []
    current = []
    for r in results:
        if r.get("t") == "di":
            if current:
                branches.append(current)
            current = []
        else:
            current.append(r)
    if current:
        branches.append(current)
    return branches


def build_choice_data(results, skill_map, se_map):
    if has_diverge(results):
        branches = split_outcomes(results)
        if len(branches) >= 2:
            s_eff, s_sk, s_cond = convert_results(branches[0], skill_map, se_map)
            f_eff, f_sk, f_cond = convert_results(branches[1], skill_map, se_map)
            return {
                "description": "",
                "outcomes": {
                    "success": {
                        "effects": s_eff,
                        "skills": s_sk,
                        "conditions": s_cond,
                    },
                    "fail": {
                        "effects": f_eff,
                        "skills": f_sk,
                        "conditions": f_cond,
                    },
                },
            }
        elif branches:
            eff, sk, cond = convert_results(branches[0], skill_map, se_map)
            return {
                "description": "",
                "effects": eff,
                "skills": sk,
                "conditions": cond,
            }
    eff, sk, cond = convert_results(results, skill_map, se_map)
    return {"description": "", "effects": eff, "skills": sk, "conditions": cond}


def process_raw_event(raw, te_names, evrew, skill_map, se_map):
    if not isinstance(raw, list) or len(raw) < 2:
        return None

    name = get_event_name(te_names, raw[0])
    if not name:
        return None

    choices_raw = raw[1]
    if choices_raw == "no" or not isinstance(choices_raw, list):
        return None

    choices = {}
    for i, ch in enumerate(choices_raw):
        if not isinstance(ch, list) or len(ch) < 2:
            continue
        reward_indices = ch[1]
        results = decode_rewards(reward_indices, evrew)
        choices[str(i + 1)] = build_choice_data(results, skill_map, se_map)

    if len(choices) < 1:
        return None

    return {"name": name, "choices": choices}


def process_char_events(data):
    te_names = data["te_names"]
    evrew = data["evrew"]
    skill_map = build_skill_map(data["skills"])
    se_map = build_status_effect_map(data["status_effects"])
    char_map = build_char_map(data["characters"])
    global_chars = build_global_char_ids(data["characters"])

    character_events = {}

    for entry in data["events_char"]:
        char_short_id = entry[0]
        if char_short_id not in global_chars:
            continue
        char_name = char_map.get(char_short_id, f"Character {char_short_id}")

        events_raw = entry[2] if len(entry) > 2 else []
        outings_raw = entry[3] if len(entry) > 3 else []

        char_events = {}
        for raw in events_raw:
            ev = process_raw_event(raw, te_names, evrew, skill_map, se_map)
            if ev:
                char_events[ev["name"]] = {"choices": ev["choices"]}

        for raw in outings_raw:
            ev = process_raw_event(raw, te_names, evrew, skill_map, se_map)
            if ev:
                char_events[ev["name"]] = {"choices": ev["choices"]}

        if char_events:
            if char_name in character_events:
                character_events[char_name].update(char_events)
            else:
                character_events[char_name] = char_events

    return character_events


def build_global_card_ids(char_cards):
    return set(
        c["card_id"]
        for c in char_cards
        if isinstance(c, dict) and c.get("release_en")
    )


def build_card_to_char_map(char_cards, char_map):
    result = {}
    for c in char_cards:
        if not isinstance(c, dict):
            continue
        card_id = c.get("card_id")
        char_id = c.get("char_id")
        if card_id and char_id:
            result[card_id] = char_map.get(char_id, f"Character {char_id}")
    return result


def process_char_card_events(data):
    te_names = data["te_names"]
    evrew = data["evrew"]
    skill_map = build_skill_map(data["skills"])
    se_map = build_status_effect_map(data["status_effects"])
    char_map = build_char_map(data["characters"])
    global_cards = build_global_card_ids(data["char_cards"])
    card_to_char = build_card_to_char_map(data["char_cards"], char_map)

    character_events = {}

    for entry in data["events_char_card"]:
        card_id = entry[0]
        if card_id not in global_cards:
            continue
        char_name = card_to_char.get(card_id, f"Card {card_id}")
        events_raw = entry[1] if len(entry) > 1 and isinstance(entry[1], list) else []

        card_events = {}
        for raw in events_raw:
            ev = process_raw_event(raw, te_names, evrew, skill_map, se_map)
            if ev:
                card_events[ev["name"]] = {"choices": ev["choices"]}

        if card_events:
            if char_name in character_events:
                character_events[char_name].update(card_events)
            else:
                character_events[char_name] = card_events

    return character_events


def format_support_name(info, support_id):
    name = info.get("name", "")
    if not name:
        return f"Support {support_id}"
    return name


SUPPORT_TYPE_MAP = {
    "speed": "Speed",
    "stamina": "Stamina",
    "power": "Power",
    "guts": "Guts",
    "intelligence": "Wit",
    "friend": "Pal",
}


def rarity_label(info, fallback):
    rarity_num = info.get("rarity", 0)
    rarity_map = {1: "R", 2: "SR", 3: "SSR"}
    rar = rarity_map.get(rarity_num, fallback)
    stype = SUPPORT_TYPE_MAP.get(info.get("type", ""), "")
    if stype:
        return f"{rar} {stype}"
    return rar


def build_shared_events_by_char(data):
    te_names = data["te_names"]
    evrew = data["evrew"]
    skill_map = build_skill_map(data["skills"])
    se_map = build_status_effect_map(data["status_effects"])

    shared_by_char = {}
    for entry in data["events_shared"]:
        char_id = entry[0]
        events_raw = entry[1]
        char_evs = {}
        for raw in events_raw:
            ev = process_raw_event(raw, te_names, evrew, skill_map, se_map)
            if ev:
                char_evs[ev["name"]] = {"choices": ev["choices"]}
        if char_evs:
            shared_by_char[char_id] = char_evs
    return shared_by_char


def process_support_events(data, source_key, fallback_rarity, shared_by_char):
    te_names = data["te_names"]
    evrew = data["evrew"]
    skill_map = build_skill_map(data["skills"])
    se_map = build_status_effect_map(data["status_effects"])
    support_map = build_support_map(data["supports"])
    global_supports = build_global_support_ids(data["supports"])

    sup_to_char = {}
    for s in data["supports"]:
        if isinstance(s, dict) and "support_id" in s:
            sup_to_char[s["support_id"]] = s.get("char_id")

    support_events = {}
    used_names = set()

    for entry in data[source_key]:
        support_id = entry[0]
        if support_id not in global_supports:
            continue
        events_raw = entry[1]

        info = support_map.get(support_id, {})
        base_name = format_support_name(info, support_id)
        rar = rarity_label(info, fallback_rarity)
        char_id = sup_to_char.get(support_id)

        card_events = {}
        if char_id and char_id in shared_by_char:
            card_events.update(shared_by_char[char_id])
        for raw in events_raw:
            ev = process_raw_event(raw, te_names, evrew, skill_map, se_map)
            if ev:
                card_events[ev["name"]] = {"choices": ev["choices"]}

        if card_events:
            display_name = f"{base_name} ({rar})"
            if display_name in used_names:
                display_name = f"{base_name} ({rar} #{support_id})"
            used_names.add(display_name)

            support_events[display_name] = {
                "type": rar,
                "support_id": support_id,
                "events": card_events,
            }

    return support_events





def _norm(name):
    return name.lower().replace(".", "").replace(" ", "").replace("\u2606", "")


_DEDUP_RACE_RE = re.compile(
    r"^(Victory!|Solid Showing|Defeat)\s*\((?:G[123]|OP and Pre-OP)\)\s*\(.*?\)$"
)
_DEDUP_CHAR_RE = re.compile(
    r"^(New Year'?s? Shrine Visit|New Year'?s? Resolutions|Extra Training"
    r"|Get Well Soon!|Don't Over Do it!)\s*\(.*?\)$"
)

_COMMON_EVENT_NAMES = {
    "Victory!", "Solid Showing", "Defeat",
    "New Year's Shrine Visit", "New Year's Resolutions",
    "Extra Training", "Get Well Soon!", "Don't Over Do it!",
}


def _extract_common_events(char_events):
    removed = 0
    common = {}
    for char_name in list(char_events.keys()):
        events = char_events[char_name]
        groups = {}
        for ename in list(events.keys()):
            m = _DEDUP_RACE_RE.match(ename) or _DEDUP_CHAR_RE.match(ename)
            if m:
                base = m.group(1)
                groups.setdefault(base, []).append(ename)
        for base, dupes in groups.items():
            if base not in common:
                canonical = events[dupes[0]]
                if base == "Extra Training":
                    c1 = canonical.get("choices", {}).get("1", {})
                    if "effects" in c1 and "speed" not in c1["effects"]:
                        c1["effects"]["speed"] = 5
                common[base] = canonical
            for d in dupes:
                del events[d]
                removed += 1
        for base in list(_COMMON_EVENT_NAMES):
            if base in events:
                if base not in common:
                    canonical = events[base]
                    if base == "Extra Training":
                        c1 = canonical.get("choices", {}).get("1", {})
                        if "effects" in c1 and "speed" not in c1["effects"]:
                            c1["effects"]["speed"] = 5
                    common[base] = canonical
                del events[base]
                removed += 1
    return common, removed


def merge_into_database(
    char_events, support_events, new_common=None,
    db_path="config/event_database.json",
):
    if os.path.exists(db_path):
        with open(db_path, "r", encoding="utf-8") as f:
            db = json.load(f)
    else:
        db = {}

    existing_common = db.get("common_events", {})
    if new_common:
        for ev_name, ev_data in new_common.items():
            if ev_name not in existing_common:
                existing_common[ev_name] = ev_data
    db["common_events"] = existing_common

    existing_chars = db.get("character_events", {})
    norm_to_existing = {_norm(k): k for k in existing_chars}
    added_char = 0
    new_chars = 0
    for char_name, events in char_events.items():
        n = _norm(char_name)
        actual_key = norm_to_existing.get(n, char_name)
        if actual_key not in existing_chars:
            existing_chars[actual_key] = events
            norm_to_existing[n] = actual_key
            added_char += len(events)
            new_chars += 1
        else:
            for ev_name, ev_data in events.items():
                if ev_name not in existing_chars[actual_key]:
                    existing_chars[actual_key][ev_name] = ev_data
                    added_char += 1
    db["character_events"] = existing_chars

    existing_sups = db.get("support_card_events", {})
    norm_to_sup = {_norm(k): k for k in existing_sups}

    added_sup = 0
    new_sups = 0
    updated_sups = 0

    for card_name, card_data in support_events.items():
        cdn_events = card_data.get("events", {})
        n = _norm(card_name)
        actual_key = norm_to_sup.get(n)

        if actual_key:
            existing = existing_sups[actual_key]
            if existing.get("type", "Unknown") == "Unknown" and card_data.get("type"):
                existing["type"] = card_data["type"]
            for ev_name, ev_data in cdn_events.items():
                if ev_name not in existing.setdefault("events", {}):
                    existing["events"][ev_name] = ev_data
                    added_sup += 1
            updated_sups += 1
        else:
            card_data.pop("support_id", None)
            existing_sups[card_name] = card_data
            norm_to_sup[n] = card_name
            new_sups += 1
            added_sup += len(cdn_events)

    db["support_card_events"] = existing_sups

    db.pop("generic_patterns", None)
    db.pop("default_strategy", None)

    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4, ensure_ascii=False)

    total_char = sum(len(v) for v in db["character_events"].values())
    total_sup = sum(len(v.get("events", {})) for v in db["support_card_events"].values())
    total_common = len(db.get("common_events", {}))
    print(f"\nMerge complete:")
    print(f"  Characters: {len(db['character_events'])} ({new_chars} new, {added_char} events added)")
    print(f"  Supports: {len(db['support_card_events'])} ({new_sups} new, {updated_sups} updated, {added_sup} events added)")
    print(f"  Common: {total_common} (preserved)")
    print(f"  Total events: {total_char} char + {total_sup} support + {total_common} common")


def main():
    print("=" * 60)
    print("Gametora CDN Event Scraper")
    print("=" * 60)

    print("\nFetching data from CDN...")
    data = fetch_cdn_data()
    global_chars = build_global_char_ids(data["characters"])
    global_sups = build_global_support_ids(data["supports"])
    global_cards = build_global_card_ids(data["char_cards"])
    print(f"  Characters: {len(data['events_char'])} ({len(global_chars)} global)")
    print(f"  Character cards: {len(data['events_char_card'])} ({len(global_cards)} global)")
    ssr_en = sum(1 for e in data['events_ssr'] if e[0] in global_sups)
    sr_en = sum(1 for e in data['events_sr'] if e[0] in global_sups)
    print(f"  SSR supports: {len(data['events_ssr'])} ({ssr_en} global)")
    print(f"  SR supports: {len(data['events_sr'])} ({sr_en} global)")
    print(f"  Shared event groups: {len(data['events_shared'])}")
    print(f"  Skills: {len(data['skills'])}")
    print(f"  Event names: {len(data['te_names'])}")

    print("\nProcessing character events...")
    char_events = process_char_events(data)
    total_c = sum(len(v) for v in char_events.values())
    print(f"  {len(char_events)} characters -> {total_c} events (shared per character)")

    print("\nProcessing character card events (costume-specific)...")
    card_events = process_char_card_events(data)
    total_cc = sum(len(v) for v in card_events.values())
    print(f"  {len(card_events)} characters -> {total_cc} card-specific events")

    for char_name, events in card_events.items():
        if char_name in char_events:
            char_events[char_name].update(events)
        else:
            char_events[char_name] = events
    total_c = sum(len(v) for v in char_events.values())
    print(f"  Combined: {len(char_events)} characters -> {total_c} events total")

    print("\nProcessing shared events (support card base events)...")
    shared_by_char = build_shared_events_by_char(data)
    total_shared = sum(len(v) for v in shared_by_char.values())
    print(f"  {len(shared_by_char)} characters -> {total_shared} base events")

    print("\nProcessing SSR support events...")
    ssr_events = process_support_events(data, "events_ssr", "SSR", shared_by_char)
    total_ssr = sum(len(v.get("events", {})) for v in ssr_events.values())
    print(f"  {len(ssr_events)} SSR cards -> {total_ssr} events (incl. base)")

    print("\nProcessing SR support events...")
    sr_events = process_support_events(data, "events_sr", "SR", shared_by_char)
    total_sr = sum(len(v.get("events", {})) for v in sr_events.values())
    print(f"  {len(sr_events)} SR cards -> {total_sr} events (incl. base)")

    all_support = {**ssr_events, **sr_events}

    new_common, deduped = _extract_common_events(char_events)
    if deduped:
        print(f"\nExtracted {len(new_common)} common events, removed {deduped} duplicates from characters")
    total_c = sum(len(v) for v in char_events.values())
    print(f"  After dedup: {len(char_events)} characters -> {total_c} events")

    print("\nMerging into event_database.json...")
    merge_into_database(char_events, all_support, new_common)

    print("Done!")


if __name__ == "__main__":
    main()
