import os
import hashlib
import shutil
import sqlite3
import platform
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==========================
# CONFIG
# ==========================

DB_FILE = "custom.db"
MIN_FILE_SIZE = 5 * 1024 # 5kb

FILE_CATEGORIES = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"},
    "Videos": {".mp4", ".avi", ".mov", ".webm"},
    "Documents": {".pdf", ".doc", ".docx", ".txt"},
    "Recording": {".wav", ".aac", ".flac"},
    "Movies": {".mkv", ".3gp", ".m4v"},
    "Music": {".mp3", ".m4a"},
    "Programs": {".exe", ".msi", ".apk", ".deb", ".rpm", ".pkg"},
    "Compressed": {".zip", ".rar", ".7z", ".tar", ".gz", ".tgz"},
    "Torrents": {".torrent"},
    "Subtitles": {".srt", ".ass", ".ssa", ".sub", ".vtt"}
}


SKIP_FOLDERS = {
    "windows",
    "program files",
    "program files (x86)",
    "programdata",
    "$recycle.bin",
    "system volume information",
    "android",
    "android_secure",
    ".android",
    ".thumbnails",
    ".trash",
    "duplicate"
}

lock = threading.Lock()


# ==========================
# DB
# ==========================

def db():
    return sqlite3.connect(DB_FILE)


def init_db():
    conn = db()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS actions(
        id INTEGER PRIMARY KEY,
        action TEXT,
        src TEXT,
        dst TEXT
    )
    """)

    conn.commit()
    conn.close()


def clear_db():
    conn = db()
    conn.execute("DELETE FROM actions")
    conn.commit()
    conn.close()


def log(src, dst):
    conn = db()

    conn.execute(
        "INSERT INTO actions(action,src,dst) VALUES(?,?,?)",
        ("MOVE", src, dst)
    )

    conn.commit()
    conn.close()


# ==========================
# UTIL
# ==========================

def is_hidden(path):

    name = os.path.basename(path)

    if name.startswith("."):
        return True

    try:
        if platform.system() == "Windows":
            import ctypes
            attrs = ctypes.windll.kernel32.GetFileAttributesW(path)
            return bool(attrs & 2)
    except:
        pass

    return False


def safe_mkdir(path):
    os.makedirs(path, exist_ok=True)


def unique(path):

    if not os.path.exists(path):
        return path

    base, ext = os.path.splitext(path)

    i = 1

    while True:

        p = f"{base}_{i}{ext}"

        if not os.path.exists(p):
            return p

        i += 1


# ==========================
# ROOTS
# ==========================

def drives():

    roots = []

    system = platform.system().lower()

    if "windows" in system:

        import string

        for d in string.ascii_uppercase:

            p = f"{d}:\\"

            if os.path.exists(p):
                roots.append(p)

    else:

        roots.append("/storage/emulated/0")

        if os.path.exists("/"):
            roots.append("/")

    return roots


def get_main_folders():

    folders = []

    for drive in drives():

        try:

            for x in os.listdir(drive):

                p = os.path.join(drive, x)

                if not os.path.isdir(p):
                    continue

                if x.lower() in SKIP_FOLDERS:
                    continue

                if is_hidden(p):
                    continue

                folders.append(p)

        except:
            pass

    return folders


def best_drive():

    best = drives()[0]
    free = 0

    for d in drives():

        try:

            st = os.statvfs(d)

            f = st.f_bavail * st.f_frsize

            if f > free:
                free = f
                best = d

        except:
            pass

    return best


# ==========================
# HASH
# ==========================

def hash_file(file):

    h = hashlib.sha256()

    try:

        with open(file, "rb") as f:

            while chunk := f.read(1024 * 1024):
                h.update(chunk)

        return h.hexdigest()

    except:
        return None


# ==========================
# CATEGORY
# ==========================

def category(file):

    ext = Path(file).suffix.lower()

    for c, exts in FILE_CATEGORIES.items():

        if ext in exts:
            return c

    return "Others"


# ==========================
# SCAN
# ==========================

def scan(root, depth):

    result = []

    base_depth = len(Path(root).parts)

    for dirpath, dirs, files in os.walk(root):

        current = len(Path(dirpath).parts)

        if current - base_depth > depth:
            continue

        dirs[:] = [

            d for d in dirs

            if (
                d.lower() not in SKIP_FOLDERS
                and not is_hidden(
                    os.path.join(dirpath, d)
                )
            )
        ]

        for f in files:

            fp = os.path.join(dirpath, f)

            try:

                if is_hidden(fp):
                    continue

                if os.path.getsize(fp) < MIN_FILE_SIZE:
                    continue

                result.append(fp)

            except:
                continue

    return result


# ==========================
# DUPLICATES
# ==========================

def find_duplicates(files):

    groups = {}

    for f in files:

        try:
            size = os.path.getsize(f)

            groups.setdefault(size, []).append(f)

        except:
            pass

    candidates = []

    for g in groups.values():

        if len(g) > 1:
            candidates.extend(g)

    hashes = {}

    with ThreadPoolExecutor(8) as ex:

        future = {
            ex.submit(hash_file, f): f
            for f in candidates
        }

        for x in as_completed(future):

            f = future[x]

            h = x.result()

            if h:
                hashes.setdefault(h, []).append(f)

    return [

        v for v in hashes.values()
        if len(v) > 1
    ]


# ==========================
# MOVE
# ==========================

def organize(file):

    cat = category(file)

    root = Path(file).anchor

    target = os.path.join(root, cat)

    safe_mkdir(target)

    dst = unique(
        os.path.join(
            target,
            os.path.basename(file)
        )
    )

    if file != dst:

        shutil.move(file, dst)

        log(file, dst)


def move_duplicates(groups):

    dup = os.path.join(
        best_drive(),
        "Duplicate"
    )

    safe_mkdir(dup)

    for g in groups:

        keep = g[0]

        for f in g:

            if f == keep:
                continue

            try:

                dst = unique(
                    os.path.join(
                        dup,
                        os.path.basename(f)
                    )
                )

                shutil.move(f, dst)

                log(f, dst)

            except:
                pass

# ==========================
# UNDO
# ==========================

def undo():

    conn = db()

    rows = conn.execute(
        """
        SELECT src,dst
        FROM actions
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    for src, dst in rows:

        try:

            if os.path.exists(dst):

                safe_mkdir(
                    os.path.dirname(src)
                )

                shutil.move(
                    dst,
                    src
                )

        except:
            pass

    print("Undo complete")  
    
# ==========================
# INPUT HELPERS
# ==========================

def ask_yes_no(msg):

    while True:

        ans = input(
            f"{msg} (y/n): "
        ).strip().lower()

        if ans in ("y", "yes"):
            return True

        if ans in ("n", "no"):
            return False

        print("Please enter y or n")


def select_folders(roots):

    while True:

        print("\n==============================")
        print(" AVAILABLE MAIN FOLDERS")
        print("==============================")

        for i, r in enumerate(roots):
            print(f"{i+1}. {r}")

        print("\nExamples:")
        print("1,3,5   → Select multiple")
        print("all     → Select everything")
        print("exit    → Cancel")

        choice = input(
            "\nSelect folders: "
        ).strip().lower()

        if choice == "exit":
            return None

        if choice == "all":
            return roots

        try:

            indexes = [
                int(x.strip()) - 1
                for x in choice.split(",")
            ]

            selected = []

            for i in indexes:

                if i < 0 or i >= len(roots):
                    raise ValueError

                selected.append(
                    roots[i]
                )

            return selected

        except:
            print(
                "\n[ERROR] Invalid selection."
            )


def ask_depth():

    while True:

        print("\nFolder Depth")

        print("0   → Only selected folder")
        print("1   → Include one level")
        print("2   → Include two levels")
        print("max → Scan everything")

        d = input(
            "\nEnter depth: "
        ).strip().lower()

        if d == "max":
            return 999

        try:

            d = int(d)

            if d >= 0:
                return d

        except:
            pass

        print("Invalid depth")


# ==========================
# SCAN PIPELINE
# ==========================

def run_scan():

    clear_db()

    print("\n==============================")
    print("     DE-DUPLICATE SCAN")
    print("==============================")

    print("""
This scan will:

• Detect duplicate files
• Move duplicates to Duplicate folder
• Organize remaining files
• Skip hidden/system folders
• Skip files under 5 KB
""")

    if not ask_yes_no(
        "\nStart scan"
    ):
        return

    roots = get_main_folders()

    if not roots:

        print(
            "\nNo folders found."
        )

        return

    selected = select_folders(
        roots
    )

    if not selected:
        return

    depth = ask_depth()

    print("\nScanning folders...\n")

    files = []

    for r in selected:

        print(
            f"[SCAN] {r}"
        )

        files.extend(
            scan(
                r,
                depth
            )
        )

    print(
        f"\n[INFO] Found {len(files)} files"
    )

    if not files:

        print(
            "Nothing to process."
        )

        return

    if not ask_yes_no(
        "\nContinue"
    ):
        return

    print(
        "\n[STEP 1/3] Finding duplicates..."
    )

    dup = find_duplicates(
        files
    )

    print(
        f"Duplicate groups: {len(dup)}"
    )

    if ask_yes_no(
        "Move duplicates"
    ):

        move_duplicates(
            dup
        )

    print(
        "\n[STEP 2/3] Organizing files..."
    )

    moved = 0

    for f in files:

        try:

            if os.path.exists(f):

                organize(f)

                moved += 1

        except:
            pass

    print(
        "\n[STEP 3/3] Finishing..."
    )

    print("\n==============================")
    print(" SCAN COMPLETE")
    print("==============================")

    print(
        f"Selected folders : {len(selected)}"
    )

    print(
        f"Files processed  : {len(files)}"
    )

    print(
        f"Duplicate groups : {len(dup)}"
    )

    print(
        f"Organized files  : {moved}"
    )

    print(
        f"Duplicate folder : "
        f"{os.path.join(best_drive(),'Duplicate')}"
    )

    input(
        "\nPress ENTER..."
    )


# ==========================
# MENU
# ==========================

def custom_menu():

    init_db()

    while True:

        print("""

=====================================
        DE-DUPLICATE ULTRA
=====================================

1 → Scan and Organize
2 → Undo Previous Scan
3 → Exit

-------------------------------------
""")

        choice = input(
            "Select option: "
        ).strip().lower()

        if choice in ("1", "scan"):

            run_scan()

        elif choice in ("2","undo" ):

            if ask_yes_no("\nUndo last scan"):
                undo()

        elif choice in ( "3", "exit", "e" ):

            print("\nExiting...")

            break

        else:

            print("\nInvalid option")

            
def run_custom_mode():
	custom_menu()