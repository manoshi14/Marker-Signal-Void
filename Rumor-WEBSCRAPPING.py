"""
Bangla Rumour Dataset - FAST Parallel Scraper (v4)
===================================================
Uses multithreading to scrape 1400 rows in 30-60 minutes.
10 parallel workers + minimal delays.

Run:  python scrape_fast.py
Deps: pip install requests beautifulsoup4 openpyxl pandas
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time, random, re, sys
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# ── CONFIG ─────────────────────────────────────────────────────────────────────
TRAIN_FILE  = "finalrumourdataset.xlsx"
VAL_TARGET  = 700
TEST_TARGET = 700
TOTAL_NEED  = VAL_TARGET + TEST_TARGET   # 1400
OUTPUT_VAL  = "val_rumour_700.xlsx"
OUTPUT_TEST = "test_rumour_700.xlsx"

WORKERS     = 10       # parallel threads
DELAY       = 0.3      # seconds between requests per thread (was 1.2-2.8)

CATEGORY_COLS = ['cultural','political','sports','religious',
                 'health','celebrity','international']

KEYWORD_CATEGORY_MAP = {
    'political':     ['নির্বাচন','শেখ হাসিনা','বিএনপি','আওয়ামী লীগ','সরকার',
                      'রাজনীতি','মন্ত্রী','সংসদ','ইউনূস','অন্তর্বর্তী','কোটা',
                      'আন্দোলন','ছাত্র','দল','নেতা'],
    'international': ['ইউক্রেন','রাশিয়া','ইসরায়েল','গাজা','আমেরিকা',
                      'ভারত','চীন','ট্রাম্প','ইরান','যুদ্ধ','পাকিস্তান','নাসা'],
    'health':        ['ক্যান্সার','ডাক্তার','হাসপাতাল','ওষুধ','ভ্যাকসিন',
                      'করোনা','ডেঙ্গু','স্বাস্থ্য','চিকিৎসা','ভিটামিন'],
    'cultural':      ['সংস্কৃতি','বৈশাখ','মেলা','ঐতিহ্য','উৎসব','পহেলা','নববর্ষ'],
    'religious':     ['ইসলাম','মসজিদ','মন্দির','ওয়াজ','হিন্দু',
                      'বৌদ্ধ','ধর্ম','কোরআন','নামাজ','আল্লাহ','হজ'],
    'sports':        ['সাকিব আল হাসান','ক্রিকেট','ফুটবল','মেসি',
                      'বিপিএল','আইপিএল','বিশ্বকাপ','খেলা','টুর্নামেন্ট'],
    'celebrity':     ['শাকিব খান','অপু বিশ্বাস','পরিমণি','হিরো আলম',
                      'মিম','চলচ্চিত্র','অভিনেত্রী','অভিনেতা','নায়িকা'],
}

# ── THREAD-SAFE SHARED STATE ───────────────────────────────────────────────────
lock        = threading.Lock()
results     = []
bl_titles   = set()
bl_urls     = set()
found_count = 0
stop_flag   = threading.Event()   # set this to stop all threads

# ── LOAD BLACKLIST ─────────────────────────────────────────────────────────────
def load_blacklist():
    global bl_titles, bl_urls
    print(f"Loading train blacklist ...")
    df = pd.read_excel(TRAIN_FILE, sheet_name='merged_rumour_dataset')
    bl_titles = set(df['text'].astype(str).str.strip().tolist())
    bl_urls   = set(df['url'].astype(str).str.strip().tolist())

    rs_ids, ja_ids = set(), set()
    for u in df['url'].dropna():
        u = str(u)
        m = re.search(r'/(\d{5,6})$', u)
        if m and 'rumorscanner' in u:
            rs_ids.add(int(m.group(1)))
        m2 = re.search(r'post-(\d+)', u)
        if m2 and 'jachai' in u:
            ja_ids.add(int(m2.group(1)))

    print(f"  {len(bl_titles)} titles blocked | RS IDs: {min(rs_ids)}-{max(rs_ids)} | Jachai max: {max(ja_ids)}")
    return rs_ids, ja_ids

# ── PER-THREAD SESSION (avoids sharing sessions across threads) ────────────────
def make_session():
    s = requests.Session()
    s.headers.update({
        'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/124.0.0.0 Safari/537.36'),
        'Accept-Language': 'bn-BD,bn;q=0.9,en;q=0.8',
    })
    return s

# ── FETCH ONE URL ──────────────────────────────────────────────────────────────
def fetch(session, url):
    try:
        time.sleep(DELAY)
        r = session.get(url, timeout=10)
        return r if r.status_code == 200 else None
    except:
        return None

# ── EXTRACT TITLE ──────────────────────────────────────────────────────────────
def extract_title(soup):
    for sel in ['h1.entry-title','h1.post-title','h1.tdb-title-text','h1']:
        t = soup.select_one(sel)
        if t:
            txt = t.get_text(strip=True)
            if len(txt) > 15:
                return txt
    og = soup.find('meta', property='og:title')
    if og and og.get('content') and len(og['content'].strip()) > 15:
        return og['content'].strip()
    return ''

def detect_categories(text):
    result = {c: 0 for c in CATEGORY_COLS}
    for cat, kws in KEYWORD_CATEGORY_MAP.items():
        if any(kw in text for kw in kws):
            result[cat] = 1
    if sum(result.values()) == 0:
        result['political'] = 1
    return result

def make_row(text, url, source):
    row = {'text': text, 'label': 0, 'source': source,
           'url': url, 'date': '2024-2026'}
    row.update(detect_categories(text))
    return row

# ── THREAD-SAFE ADD RESULT ─────────────────────────────────────────────────────
def try_add(title, url, source):
    global found_count
    if stop_flag.is_set():
        return False
    with lock:
        if title in bl_titles or url in bl_urls or len(title) < 15:
            return False
        # Filter out site homepage titles
        if title.lower() in ['rumor scanner – fact check bangladesh',
                              'jachai', 'boom bangladesh', 'boombd']:
            return False
        row = make_row(title, url, source)
        results.append(row)
        bl_titles.add(title)
        bl_urls.add(url)
        found_count += 1
        print(f"  [{found_count:4d}/{TOTAL_NEED}] [{source[:2]}] {title[:70]}")
        if found_count >= TOTAL_NEED:
            stop_flag.set()
        return True

# ══════════════════════════════════════════════════════════════════════════════
#  WORKER: RumorScanner by ID (each thread handles a chunk of IDs)
# ══════════════════════════════════════════════════════════════════════════════
def rs_worker(id_chunk, train_rs_ids):
    session = make_session()
    for nid in id_chunk:
        if stop_flag.is_set():
            break
        if nid in train_rs_ids:
            continue

        r = fetch(session, f"https://rumorscanner.com/?p={nid}")
        if r is None:
            continue

        final_url = r.url
        # Must redirect to a fact-check article
        if 'fact-check' not in final_url:
            continue

        soup  = BeautifulSoup(r.content, 'html.parser')
        title = extract_title(soup)
        try_add(title, final_url, 'Rumor Scanner')

# ══════════════════════════════════════════════════════════════════════════════
#  WORKER: Jachai by ID (gap IDs + new IDs)
# ══════════════════════════════════════════════════════════════════════════════
def jachai_worker(id_chunk, train_ja_ids):
    session = make_session()
    for jid in id_chunk:
        if stop_flag.is_set():
            break
        if jid in train_ja_ids:
            continue

        url = f"https://jachai.org/fact-checks/post-{jid}"
        r   = fetch(session, url)
        if r is None:
            continue

        soup  = BeautifulSoup(r.content, 'html.parser')
        title = extract_title(soup)
        try_add(title, url, 'Jachai')

# ══════════════════════════════════════════════════════════════════════════════
#  WORKER: BoomBD paginated listing
# ══════════════════════════════════════════════════════════════════════════════
def boombd_worker(page_chunk):
    session = make_session()
    for page in page_chunk:
        if stop_flag.is_set():
            break

        r = fetch(session, f"https://www.boombd.com/fake-news?page={page}")
        if r is None:
            continue

        soup   = BeautifulSoup(r.content, 'html.parser')
        a_tags = soup.find_all('a', href=re.compile(r'/n-\d+'))

        for a in a_tags:
            if stop_flag.is_set():
                break
            href = a.get('href', '')
            if not href.startswith('http'):
                href = f"https://www.boombd.com{href}"
            with lock:
                if href in bl_urls:
                    continue

            ar = fetch(session, href)
            if ar is None:
                continue
            soup2 = BeautifulSoup(ar.content, 'html.parser')
            title = extract_title(soup2)
            try_add(title, href, 'Boom Bangladesh')

# ══════════════════════════════════════════════════════════════════════════════
#  SPLIT IDs INTO CHUNKS FOR PARALLEL WORKERS
# ══════════════════════════════════════════════════════════════════════════════
def chunk(lst, n):
    size = max(1, len(lst) // n)
    return [lst[i:i+size] for i in range(0, len(lst), size)]

# ══════════════════════════════════════════════════════════════════════════════
#  SAVE OUTPUT
# ══════════════════════════════════════════════════════════════════════════════
def save_dataset(rows, filename):
    cols = ['text','label','source','url','date'] + CATEGORY_COLS
    df   = pd.DataFrame(rows)
    for c in CATEGORY_COLS:
        if c not in df.columns:
            df[c] = 0
    df = df[cols].drop_duplicates(subset=['text']).reset_index(drop=True)
    df.to_excel(filename, index=False)
    print(f"\n>>> SAVED '{filename}'  ({len(df)} rows)")
    for c in CATEGORY_COLS:
        n = int(df[c].sum())
        if n > 0:
            print(f"      {c}: {n}")
    return df

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    train_rs_ids, train_ja_ids = load_blacklist()

    rs_max = max(train_rs_ids)   # 187527
    rs_min = min(train_rs_ids)   # 22700
    ja_max = max(train_ja_ids)   # 3851

    # Build ID lists
    rs_new  = list(range(rs_max + 1, rs_max + 8000))         # above train
    rs_old  = list(range(rs_min - 1, max(1, rs_min-15000), -1))  # below train
    rs_all  = rs_new + rs_old

    ja_gaps = [i for i in range(1, ja_max + 1) if i not in train_ja_ids]
    random.shuffle(ja_gaps)
    ja_new  = list(range(ja_max + 1, ja_max + 3000))
    ja_all  = ja_gaps + ja_new

    boom_pages = list(range(50, 300))

    print(f"\nStarting parallel scrape with {WORKERS} workers")
    print(f"  RS IDs to try : {len(rs_all):,}  (new: {len(rs_new)}, old: {len(rs_old)})")
    print(f"  Jachai IDs    : {len(ja_all):,}  (gaps: {len(ja_gaps)}, new: {len(ja_new)})")
    print(f"  BoomBD pages  : {len(boom_pages)}")
    print(f"  Target        : {TOTAL_NEED} rows\n")

    start_time = time.time()

    # Split each source across workers
    # Allocate workers: 5 RS, 3 Jachai, 2 BoomBD
    rs_chunks    = chunk(rs_all,    5)
    jachai_chunks= chunk(ja_all,    3)
    boom_chunks  = chunk(boom_pages,2)

    futures = []
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        for c in rs_chunks:
            futures.append(executor.submit(rs_worker, c, train_rs_ids))
        for c in jachai_chunks:
            futures.append(executor.submit(jachai_worker, c, train_ja_ids))
        for c in boom_chunks:
            futures.append(executor.submit(boombd_worker, c))

        # Wait for all to finish or stop_flag set
        for f in as_completed(futures):
            try:
                f.result()
            except Exception as e:
                print(f"  Thread error: {e}")

    elapsed = time.time() - start_time
    print(f"\nScraping done in {elapsed/60:.1f} minutes")
    print(f"Total collected: {len(results)}")

    if len(results) < TOTAL_NEED:
        print(f"⚠ Only {len(results)} rows — increase ID ranges or add more sources.")

    # Deduplicate one final time
    seen_t, seen_u, clean = set(), set(), []
    for row in results:
        t, u = row['text'], row['url']
        if t not in seen_t and u not in seen_u:
            clean.append(row)
            seen_t.add(t)
            seen_u.add(u)

    random.shuffle(clean)
    val_rows  = clean[:VAL_TARGET]
    test_rows = clean[VAL_TARGET:VAL_TARGET + TEST_TARGET]

    save_dataset(val_rows,  OUTPUT_VAL)
    save_dataset(test_rows, OUTPUT_TEST)

    print(f"\n{'='*55}")
    print(f"Val  : {len(val_rows)} rows  →  {OUTPUT_VAL}")
    print(f"Test : {len(test_rows)} rows  →  {OUTPUT_TEST}")
    print(f"Time : {elapsed/60:.1f} minutes")

if __name__ == "__main__":
    main()
