# De-Duplicate

A cross-platform Python script for removing duplicate images and videos using SHA256 hashing.

Works on:

- Termux (Android)
- Windows
- Linux
- macOS

---

# Features

- Detects duplicates using SHA256 hash
- Works even if filenames are changed
- Deletes duplicate files automatically
- Sorts unique files into folders
- Recursive folder scanning
- Cross-platform support
- Lightweight and fast
- Easy to extend later

---


# Current Supported File Types

## Images

- jpg
- jpeg
- png
- gif
- bmp
- webp
- tiff
- heic

## Videos

- mp4
- mkv
- avi
- mov
- wmv
- flv
- webm
- m4v


# Project Structure

```text
De-Duplicate/
├── main.py
├── Raw/
├── Filtered/
│   ├── Images/
│   └── Videos/
├── README.md
└── requirements.txt
