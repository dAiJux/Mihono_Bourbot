import urllib.request
import re
import json
import sys
import time
import ssl
import os

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ssl._create_default_https_context = ssl._create_unverified_context

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def fetch_page(url, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode('utf-8', errors='replace')
        except Exception as e:
            print(f"  Retry {attempt+1}/{retries} for {url}: {e}")
            time.sleep(2)
    return None

def extract_event_links(html):
    pattern = r'<a[^>]*href="(/games/Umamusume-Pretty-Derby/archives/(\d+))"[^>]*>([^<]+)</a>'
    links = re.findall(pattern, html)
    return links

def extract_trainee_event_mapping(html):
    tables = re.findall(r'<table[^>]*a-table[^>]*>(.*?)</table>', html, re.DOTALL)
    trainee_table = None
    for t in tables:
        if 'Trainee' in t:
            trainee_table = t
            break
    if not trainee_table:
        return {}

    results = {}
    rows = re.findall(r'<tr>(.*?)</tr>', trainee_table, re.DOTALL)

    for row in rows:
        if 'Trainee' not in row:
            continue

        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if len(cells) < 3:
            continue

        type_cell = cells[1]
        if 'Trainee' not in type_cell:
            continue

        char_alts = re.findall(r'alt="([^"]+?)\s*Image"', cells[0])
        if not char_alts:
            continue

        base_names = set()
        for alt in char_alts:
            base = re.sub(r'\s*\([^)]*\)\s*$', '', alt).strip()
            if base:
                base_names.add(base)

        event_match = re.search(
            r'href="https://game8\.co/games/Umamusume-Pretty-Derby/archives/(\d+)"[^>]*>([^<]+)</a>',
            cells[2]
        )
        if not event_match:
            continue

        archive_id = event_match.group(1)
        event_name = event_match.group(2).strip()

        for char_name in base_names:
            if char_name not in results:
                results[char_name] = []
            results[char_name].append({
                'event_name': event_name,
                'archive_id': archive_id,
            })

    return results

def extract_card_event_mapping(html):
    results = {}
    
    row_pattern = r'<tr>(.*?)</tr>'
    rows = re.findall(row_pattern, html, re.DOTALL)
    
    for row in rows:
        card_alts = re.findall(r"alt='([^']+?)\s*Image'", row)
        card_names = [a.strip() for a in card_alts]
        
        event_match = re.search(
            r"href=https://game8\.co/games/Umamusume-Pretty-Derby/archives/(\d+)>([^<]+)</a>\s*</td>",
            row
        )
        
        if card_names and event_match:
            archive_id = event_match.group(1)
            event_name = event_match.group(2).strip()
            
            primary_card = card_names[0]
            
            if primary_card not in results:
                results[primary_card] = []
            results[primary_card].append({
                'event_name': event_name,
                'archive_id': archive_id,
                'all_cards': card_names
            })
    
    return results

def parse_effects(outcome_html):
    effects = {}
    text = re.sub(r'<[^>]+>', ' ', outcome_html)

    stat_patterns = {
        'speed': r'[-+]?\s*(\d+)\s*Speed',
        'stamina': r'[-+]?\s*(\d+)\s*Stamina',
        'power': r'[-+]?\s*(\d+)\s*Power',
        'guts': r'[-+]?\s*(\d+)\s*Guts',
        'wit': r'[-+]?\s*(\d+)\s*(?:Wis(?:dom)?|Wit)',
        'energy': r'[-+]?\s*(\d+)\s*(?<!Max\s)Energy',
        'max_energy': r'[-+]?\s*(\d+)\s*Max\s*Energy',
        'skill_pts': r'[-+]?\s*(\d+)\s*Skill\s*Pt',
        'friendship': r'[-+]?\s*(\d+)\s*Friendship',
        'mood': r'[-+]?\s*(\d+)\s*(?:Mood|Motivation)',
    }

    for stat, pat in stat_patterns.items():
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = int(m.group(1))
            neg_pat = r'(-)\s*' + str(val) + r'\s*'
            if stat == 'max_energy':
                neg_pat += r'Max\s*Energy'
            elif stat == 'energy':
                neg_pat += r'(?!Max)Energy'
            else:
                neg_pat += stat.replace('_', r'\s*')
            full = re.search(neg_pat, text, re.IGNORECASE)
            if full:
                val = -val
            effects[stat] = val

    all_stats_match = re.search(r'[-+]?\s*(\d+)\s*All\s*Stats', text, re.IGNORECASE)
    if all_stats_match:
        val = int(all_stats_match.group(1))
        neg = re.search(r'(-)\s*' + str(val) + r'\s*All\s*Stats', text, re.IGNORECASE)
        if neg:
            val = -val
        for stat in ('speed', 'stamina', 'power', 'guts', 'wit'):
            if stat not in effects:
                effects[stat] = val

    skills = []
    for m in re.finditer(r'(?:・|\u30FB|\u00B7)\s*([^・\u30FB\u00B7]+?)\s*(?:[\u25CB\u25CE\u25CF\u25EF]\s*)?\+?(\d+)?\s*Skill\s*Hint', text, re.IGNORECASE):
        name = re.sub(r'[\u25CB\u25CE\u25CF\u25EF\u25A0\u25A1\u25B2\u25B3]+', '', m.group(1)).strip()
        level = int(m.group(2)) if m.group(2) else 1
        if name and not re.match(r'^\d+$', name):
            skills.append({"name": name, "level": level})

    conditions = []
    cond_patterns = [
        r'(Practice\s+Perfect|Practice\s+Poor|Practice\s+Bad|Charming|Fast\s+Learner|'
        r'Night\s+Owl|Slow\s+Metabolism|Overweight|Fragile|Lazy|'
        r'Sharp|Good\s+Practice|Headstrong)',
    ]
    for pat in cond_patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            cond = m.group(1).strip()
            if cond not in conditions:
                conditions.append(cond)

    return effects, skills, conditions

def extract_event_choices(html, event_name):
    choices = []

    table_match = re.search(
        r"<table\s+class=['\"]a-table[^>]*>.*?<th[^>]*>\s*Choice\s*</th>\s*<th[^>]*>\s*Outcome\s*</th>.*?</table>",
        html, re.DOTALL
    )
    if not table_match:
        return []

    table_html = table_match.group()

    if re.search(r"No\s*Choices", table_html):
        outcome_match = re.search(r"No\s*Choices.*?</td>\s*<td[^>]*>(.*?)</td>", table_html, re.DOTALL)
        if outcome_match:
            effects, skills, conditions = parse_effects(outcome_match.group(1))
            choices.append({
                'choice_num': 0,
                'variant': 'auto',
                'description': 'auto',
                'effects': effects,
                'skills': skills,
                'conditions': conditions,
            })
        return choices

    rows = re.findall(r'<tr>(.*?)</tr>', table_html, re.DOTALL)
    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if len(cells) < 2:
            continue

        choice_cell = cells[0]
        outcome_cell = cells[1]

        choice_match = re.search(r"<b\s+class=['\"]a-bold['\"]>\s*Choice\s+(\d+)\s*</b>", choice_cell)
        if not choice_match:
            continue

        choice_num = int(choice_match.group(1))

        variant = ''
        variant_match = re.search(r'\(\s*(Success|Fail)\s*\)', choice_cell, re.IGNORECASE)
        if variant_match:
            variant = variant_match.group(1).strip().lower()

        description = ''
        desc_match = re.search(r'<hr[^>]*>\s*\(([^)]*)\)', choice_cell)
        if desc_match:
            description = desc_match.group(1).strip()

        effects, skills, conditions = parse_effects(outcome_cell)
        choices.append({
            'choice_num': choice_num,
            'variant': variant,
            'description': description,
            'effects': effects,
            'skills': skills,
            'conditions': conditions,
        })

    return choices

def build_choices_data(choices):
    if not choices:
        return {}

    result = {}
    for c in choices:
        num = str(c['choice_num'])
        variant = c.get('variant', '') or ''
        entry = {
            "description": c.get('description', ''),
            "effects": c['effects'],
            "skills": c.get('skills', []),
            "conditions": c.get('conditions', []),
        }

        if variant in ('success', 'fail'):
            if num not in result:
                result[num] = {
                    "description": c.get('description', ''),
                    "outcomes": {}
                }
            elif "outcomes" not in result[num]:
                existing = result[num]
                result[num] = {
                    "description": existing.get("description", ""),
                    "outcomes": {
                        "default": {
                            "effects": existing.get("effects", {}),
                            "skills": existing.get("skills", []),
                            "conditions": existing.get("conditions", []),
                        }
                    }
                }
            result[num]["outcomes"][variant] = {
                "effects": c['effects'],
                "skills": c.get('skills', []),
                "conditions": c.get('conditions', []),
            }
        else:
            result[num] = entry

    return result

SSR_CARDS = {
    "Sasami Anshinzawa (This Might Sting!)": "SSR Speed",
    "Matikanefukukitaru (Touching Sleeves Is Good Luck!)": "SSR Speed",
    "Silence Suzuka (Searching for Unseen Sights)": "SSR Speed",
    "Mayano Top Gun (Party Formation)": "SSR Speed",
    "Zenno Rob Roy (Magical Heroine)": "SSR Speed",
    "Sweep Tosho (It's All Mine!)": "SSR Speed",
    "Narita Brian (Two Pieces)": "SSR Speed",
    "Gold Ship (That Time I Became the Strongest)": "SSR Speed",
    "Kawakami Princess (Princess Bride)": "SSR Speed",
    "Kitasan Black (Fire at My Heels)": "SSR Speed",
    "Special Week (The Setting Sun and Rising Stars)": "SSR Speed",
    "Twin Turbo (Turbo Booooost!)": "SSR Speed",
    "Biko Pegasus (Double Carrot Punch!)": "SSR Speed",
    "Nishino Flower (Even the Littlest Bud)": "SSR Speed",
    "Sakura Bakushin O (Eat Fast! Yum Fast!)": "SSR Speed",
    "Gold City (Run (my) way)": "SSR Speed",
    "Tokai Teio (Dream Big!)": "SSR Speed",
    "Silence Suzuka (Beyond This Shining Moment)": "SSR Speed",
    "Meisho Doto (Leaping into the Unknown)": "SSR Stamina",
    "Manhattan Cafe (My Solo Spun in Spiraling Runs)": "SSR Stamina",
    "Narita Brian (The Whistling Arrow's Taunt)": "SSR Stamina",
    "Nakayama Festa (43, 8, 1)": "SSR Stamina",
    "Silence Suzuka (Winning Dream)": "SSR Stamina",
    "Winning Ticket (Full-Blown Tantrum)": "SSR Stamina",
    "Sakura Chiyono O (Peak Sakura Season)": "SSR Stamina",
    "Satono Diamond (The Will to Overtake)": "SSR Stamina",
    "Rice Shower (Showered in Joy)": "SSR Stamina",
    "Mejiro McQueen (Your Team Ace)": "SSR Stamina",
    "Super Creek (Piece of Mind)": "SSR Stamina",
    "Tamamo Cross (Split the Sky, White Lightning!)": "SSR Stamina",
    "Seiun Sky (Foolproof Plan)": "SSR Stamina",
    "Gold Ship (Breakaway Battleship)": "SSR Stamina",
    "Admire Vega (Lucky Star in the Sky)": "SSR Power",
    "Bamboo Memory (Head-On Fight!)": "SSR Power",
    "Daitaku Helios (Make! Some! NOISE!)": "SSR Power",
    "Daiwa Scarlet (Mini Vacation)": "SSR Power",
    "El Condor Pasa (Champion's Passion)": "SSR Power",
    "King Halo (Tonight, We Waltz)": "SSR Power",
    "Marvelous Sunday (Dazzling Day in the Snow)": "SSR Power",
    "Oguri Cap (Get Lots of Hugs for Me)": "SSR Power",
    "Rice Shower (Happiness Just around the Bend)": "SSR Power",
    "Smart Falcon (My Umadol Way!)": "SSR Power",
    "Tamamo Cross (Beware! Halloween Night!)": "SSR Power",
    "Vodka (Wild Rider)": "SSR Power",
    "Winning Ticket (Dreams Do Come True!)": "SSR Power",
    "Yaeno Muteki (Fiery Discipline)": "SSR Power",
    "Yukino Bijin (Dancing Light into the Night)": "SSR Guts",
    "Ikuno Dictus (Warm Heart, Soft Steps)": "SSR Guts",
    "Mejiro Ryan (Winning Pitch)": "SSR Guts",
    "Hishi Akebono (Who Wants the First Bite?)": "SSR Guts",
    "Matikane Tannhauser (Just Keep Going)": "SSR Guts",
    "Mejiro Palmer (Go Ahead and Laugh)": "SSR Guts",
    "Haru Urara (Urara's Day Off!)": "SSR Guts",
    "Winning Ticket (BNWinner!)": "SSR Guts",
    "Ines Fujin (Watch My Star Fly!)": "SSR Guts",
    "Grass Wonder (Fairest Fleur)": "SSR Guts",
    "Special Week (The Brightest Star in Japan)": "SSR Guts",
    "Narita Taishin (Strict Shopper)": "SSR Wit",
    "Curren Chan (Cutie Pie with Shining Eyes)": "SSR Wit",
    "Mihono Bourbon (The Ghost Finds Halloween Magic)": "SSR Wit",
    "Nice Nature (Daring to Dream)": "SSR Wit",
    "Seiun Sky (Paint the Sky Red)": "SSR Wit",
    "Mejiro Dober (My Thoughts, My Desires)": "SSR Wit",
    "Yukino Bijin (Hometown Cheers)": "SSR Wit",
    "Air Shakur (7 More Centimeters)": "SSR Wit",
    "Fine Motion (Wave of Gratitude)": "SSR Wit",
    "Sasami Anshinzawa (Pal SSR)": "SSR Pal",
    "Riko Kashimoto (Planned Perfection)": "SSR Pal",
    "Tazuna Hayakawa (Tracen Reception)": "SSR Pal",
}

EXISTING_CARDS = [
    "Kitasan Black (Fire at My Heels)",
    "Super Creek (Piece of Mind)",
    "Mejiro McQueen (Your Team Ace)",
    "Silence Suzuka (Beyond This Shining Moment)",
    "Tokai Teio (Dream Big!)",
    "Rice Shower (Happiness Just around the Bend)",
    "Sakura Bakushin O (Eat Fast! Yum Fast!)",
    "Daiwa Scarlet (Mini Vacation)",
    "Vodka (Wild Rider)",
    "Gold Ship (Breakaway Battleship)",
    "Narita Brian (Two Pieces)",
]

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode in ("all", "support"):
        scrape_support_events()
    if mode in ("all", "trainee"):
        scrape_trainee_events()

def scrape_support_events():
    print("=" * 60)
    print("Umamusume Support Card Event Scraper")
    print("=" * 60)

    print("\n[1/4] Fetching support card events list page...")
    events_page = fetch_page("https://game8.co/games/Umamusume-Pretty-Derby/archives/539720")
    if not events_page:
        print("ERROR: Could not fetch events list page")
        return

    print("\n[2/4] Extracting event links...")
    card_events = extract_card_event_mapping(events_page)
    print(f"  Found {len(card_events)} cards with events")

    progress_file = "config/scraped_support_events.json"
    try:
        with open(progress_file, "r", encoding="utf-8") as f:
            all_card_data = json.load(f).get("support_card_events", {})
        print(f"  Loaded {len(all_card_data)} cards from previous run")
    except:
        all_card_data = {}

    print("\n[3/4] Fetching individual event pages...")
    total_events = 0
    fetched = 0
    skipped = 0

    for card_name, events in sorted(card_events.items()):
        if card_name in all_card_data and len(all_card_data[card_name].get("events", {})) == len(events):
            skipped += len(events)
            continue

        card_type = "Unknown"
        for ssr_name, ssr_type in SSR_CARDS.items():
            cn = card_name.replace('\u2019', "'").replace('\u2606', '').strip()
            if cn == ssr_name or ssr_name == cn or \
               cn.split('(')[0].strip() == ssr_name.split('(')[0].strip():
                card_type = ssr_type
                break

        card_data = {
            "type": card_type,
            "events": {}
        }

        for event_info in events:
            event_name = event_info['event_name']
            archive_id = event_info['archive_id']
            total_events += 1

            url = f"https://game8.co/games/Umamusume-Pretty-Derby/archives/{archive_id}"
            print(f"  [{fetched+1}] {card_name} -> {event_name} ({archive_id})...")

            html = fetch_page(url)
            fetched += 1

            if html:
                choices = extract_event_choices(html, event_name)
                all_choices = build_choices_data(choices)

                card_data["events"][event_name] = {
                    "choices": all_choices
                }

                if choices and choices[0]['choice_num'] != 0:
                    print(f"    -> {len(all_choices)} choices")
                elif choices:
                    print(f"    -> Auto-event")
                else:
                    print(f"    -> No choices parsed")
                    card_data["events"][event_name] = {"choices": {}}
            else:
                print(f"    -> FAILED to fetch")
                card_data["events"][event_name] = {"choices": {}}

            time.sleep(0.3)

        all_card_data[card_name] = card_data

        with open(progress_file, "w", encoding="utf-8") as f:
            json.dump({"support_card_events": all_card_data}, f, indent=4, ensure_ascii=False)

    print(f"\n[4/4] Done! ({fetched} fetched, {skipped} skipped)")
    print(f"Total cards: {len(all_card_data)}")

    with open(progress_file, "w", encoding="utf-8") as f:
        json.dump({"support_card_events": all_card_data}, f, indent=4, ensure_ascii=False)

    print(f"Saved to {progress_file}")

def scrape_trainee_events():
    print("=" * 60)
    print("Umamusume Trainee (Character) Event Scraper")
    print("=" * 60)

    print("\n[1/5] Fetching master events list page (539612)...")
    events_page = fetch_page("https://game8.co/games/Umamusume-Pretty-Derby/archives/539612")
    if not events_page:
        print("ERROR: Could not fetch events list page")
        return

    print("\n[2/5] Extracting trainee event links...")
    char_events = extract_trainee_event_mapping(events_page)
    total_count = sum(len(evts) for evts in char_events.values())
    print(f"  Found {len(char_events)} characters with {total_count} trainee events")

    shared_events = {}
    unique_events = {}
    for char_name, events in char_events.items():
        for evt in events:
            base = re.sub(r'\s*\([^)]*\)\s*$', '', evt['event_name'])
            if base != evt['event_name']:
                if base not in shared_events:
                    shared_events[base] = []
                shared_events[base].append({
                    'char': char_name,
                    'full_name': evt['event_name'],
                    'archive_id': evt['archive_id'],
                })
            else:
                if char_name not in unique_events:
                    unique_events[char_name] = []
                unique_events[char_name].append(evt)

    shared_multi = {b: entries for b, entries in shared_events.items() if len(entries) > 1}
    shared_single = {b: entries[0] for b, entries in shared_events.items() if len(entries) == 1}

    shared_pages = len(shared_multi)
    unique_pages = sum(len(evts) for evts in unique_events.values())
    single_pages = len(shared_single)
    total_pages = shared_pages + unique_pages + single_pages
    saved = total_count - total_pages

    print(f"  Shared events (dedup): {len(shared_multi)} base events across {sum(len(e) for e in shared_multi.values())} references")
    print(f"  Pages to fetch: {total_pages} (saved {saved} via dedup)")

    progress_file = "config/scraped_trainee_events.json"
    try:
        with open(progress_file, "r", encoding="utf-8") as f:
            all_char_data = json.load(f).get("character_events", {})
        print(f"  Loaded {len(all_char_data)} characters from previous run")
    except:
        all_char_data = {}

    print("\n[3/5] Fetching shared events (one per group)...")
    fetched = 0
    skipped = 0
    shared_cache = {}

    for base_name, entries in sorted(shared_multi.items()):
        first = entries[0]

        already_cached = False
        for entry in entries:
            existing = all_char_data.get(entry['char'], {})
            if entry['full_name'] in existing and existing[entry['full_name']].get('choices'):
                shared_cache[base_name] = existing[entry['full_name']]
                already_cached = True
                break

        if already_cached:
            skipped += 1
            continue

        url = f"https://game8.co/games/Umamusume-Pretty-Derby/archives/{first['archive_id']}"
        print(f"  [{fetched+1}] {base_name} ({first['archive_id']})...")

        html = fetch_page(url)
        fetched += 1

        if html:
            choices = extract_event_choices(html, first['full_name'])
            all_choices = build_choices_data(choices)
            shared_cache[base_name] = {"choices": all_choices}

            if choices and choices[0]['choice_num'] != 0:
                print(f"    -> {len(all_choices)} choices")
            elif choices:
                print(f"    -> Auto-event")
            else:
                print(f"    -> No choices parsed")
                shared_cache[base_name] = {"choices": {}}
        else:
            print(f"    -> FAILED to fetch")
            shared_cache[base_name] = {"choices": {}}

        time.sleep(0.3)

    print(f"\n  Shared: {fetched} fetched, {skipped} cached")

    print("\n[4/5] Applying shared events to all characters...")
    for base_name, entries in shared_multi.items():
        if base_name not in shared_cache:
            continue
        event_data = shared_cache[base_name]
        for entry in entries:
            char_name = entry['char']
            if char_name not in all_char_data:
                all_char_data[char_name] = {}
            all_char_data[char_name][entry['full_name']] = event_data

    for base_name, entry in shared_single.items():
        char_name = entry['char']
        existing = all_char_data.get(char_name, {})
        if entry['full_name'] in existing and existing[entry['full_name']].get('choices'):
            skipped += 1
            continue

        url = f"https://game8.co/games/Umamusume-Pretty-Derby/archives/{entry['archive_id']}"
        print(f"  [{fetched+1}] {char_name} -> {entry['full_name']} ({entry['archive_id']})...")

        html = fetch_page(url)
        fetched += 1

        if html:
            choices = extract_event_choices(html, entry['full_name'])
            all_choices = build_choices_data(choices)
            if char_name not in all_char_data:
                all_char_data[char_name] = {}
            all_char_data[char_name][entry['full_name']] = {"choices": all_choices}
            if choices and choices[0]['choice_num'] != 0:
                print(f"    -> {len(all_choices)} choices")
            elif choices:
                print(f"    -> Auto-event")
            else:
                print(f"    -> No choices parsed")
                all_char_data[char_name][entry['full_name']] = {"choices": {}}
        else:
            print(f"    -> FAILED to fetch")
            if char_name not in all_char_data:
                all_char_data[char_name] = {}
            all_char_data[char_name][entry['full_name']] = {"choices": {}}

        time.sleep(0.3)

    with open(progress_file, "w", encoding="utf-8") as f:
        json.dump({"character_events": all_char_data}, f, indent=4, ensure_ascii=False)

    print(f"\n[5/5] Fetching unique character events...")
    for char_name, events in sorted(unique_events.items()):
        existing = all_char_data.get(char_name, {})

        char_data = dict(existing)

        for event_info in events:
            event_name = event_info['event_name']
            archive_id = event_info['archive_id']

            if event_name in char_data and char_data[event_name].get('choices'):
                skipped += 1
                continue

            url = f"https://game8.co/games/Umamusume-Pretty-Derby/archives/{archive_id}"
            print(f"  [{fetched+1}] {char_name} -> {event_name} ({archive_id})...")

            html = fetch_page(url)
            fetched += 1

            if html:
                choices = extract_event_choices(html, event_name)
                all_choices = build_choices_data(choices)

                char_data[event_name] = {"choices": all_choices}

                if choices and choices[0]['choice_num'] != 0:
                    print(f"    -> {len(all_choices)} choices")
                elif choices:
                    print(f"    -> Auto-event")
                else:
                    print(f"    -> No choices parsed")
                    char_data[event_name] = {"choices": {}}
            else:
                print(f"    -> FAILED to fetch")
                char_data[event_name] = {"choices": {}}

            time.sleep(0.3)

        all_char_data[char_name] = char_data

        with open(progress_file, "w", encoding="utf-8") as f:
            json.dump({"character_events": all_char_data}, f, indent=4, ensure_ascii=False)

    print(f"\nDone! ({fetched} fetched, {skipped} skipped)")
    print(f"Total characters: {len(all_char_data)}")

    with open(progress_file, "w", encoding="utf-8") as f:
        json.dump({"character_events": all_char_data}, f, indent=4, ensure_ascii=False)

    print(f"Saved to {progress_file}")

if __name__ == "__main__":
    main()
