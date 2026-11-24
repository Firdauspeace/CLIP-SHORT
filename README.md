# CLIP SHORT

1. Buka `CLIP SHORT Studio.exe` pada Windows 64-bit.
2. Tampal pautan video YouTube, Facebook, TikTok atau Instagram, atau klik **Pilih video** untuk membuka fail tempatan.
3. Dalam **Studio**, pilih tindakan dan folder hasil, kemudian klik **Mula**. Folder lalai ialah `Exports` di sebelah aplikasi.
4. Klik klip pada garis masa atau senarai hasil untuk melihat pratonton. Klik **Main video** untuk membuka klip dalam pemain lalai Windows.

**Pustaka** menyenaraikan fail video dalam folder hasil yang dipilih. **Gaya** menawarkan lima warna aksen untuk antaramuka.

| Tindakan | Hasil |
| --- | --- |
| Muat turun sahaja | Simpan video daripada pautan. Pilih kualiti Terbaik, 1080p, 720p atau 480p. Resolusi bergantung pada pilihan yang disediakan oleh platform. |
| Render penuh | Eksport seluruh video sebagai MP4 H.264 pada 30 fps. |
| Potong manual | Tetapkan masa mula dan akhir, contohnya `00:15` hingga `00:42`. Biarkan masa akhir kosong untuk sambung sampai hujung video. |
| Auto-cut | Pecahkan video kepada beberapa MP4 dengan durasi sasaran antara 5 dan 180 saat. Aplikasi utamakan jeda audio berhampiran titik potong. Jika tiada jeda, aplikasi potong mengikut masa. Klip dikeluarkan mengikut turutan asal. |

Untuk render, pilih **9:16**, **16:9**, **1:1**, **4:5** atau **Nisbah asal**. Mod **Muatkan semua** kekalkan keseluruhan bingkai dan tambah ruang hitam apabila perlu. Mod **Crop tengah** isi bingkai dengan memotong bahagian tepi.

## Keperluan

EXE menyertakan Python/Tkinter dan `yt-dlp` Windows 2026.11.23. Aplikasi menggunakan FFmpeg dan FFprobe melalui `PATH` atau dari folder `bin` di sebelah EXE. Kedua-duanya sudah ditemui pada PC ini. Aplikasi menggunakan Node.js jika tersedia untuk pemprosesan YouTube. Untuk kemas kini enjin muat turun, letakkan `yt-dlp.exe` baharu dalam folder `bin`. [FFmpeg](https://ffmpeg.org/download.html) · [yt-dlp](https://github.com/yt-dlp/yt-dlp/releases) · [Node.js](https://nodejs.org/en/download)

Gunakan video yang anda miliki atau dibenarkan untuk muat turun. Kebolehcapaian bergantung pada pautan dan platform. Jika pautan gagal tetapi anda ada fail videonya, guna **Pilih video** untuk potong atau render fail itu.

## Semakan AutoClip Studio

Pemasang rujukan dikenal pasti sebagai Inno Setup 6.7.0. Semakan statik terhadap salinan terpasang menyenaraikan 485 fail dalam arkib Nuitka, termasuk Python 3.12, antaramuka web, FFmpeg/FFprobe, yt-dlp dan faster-whisper. Antaramuka asal meliputi penciptaan klip, pustaka, tetapan jenama, garis masa, editor teks kapsyen dan skor klip. CLIP SHORT menggunakan kod dan reka bentuk desktop sendiri untuk aliran muat turun, potong, pratonton dan eksport. Auto-cut memilih titik potong berdasarkan durasi dan jeda audio. [Dokumentasi penapis FFmpeg](https://ffmpeg.org/ffmpeg-filters.html#silencedetect)

## Bina EXE daripada kod sumber

Pasang Python 3.12 dengan Tkinter, PyInstaller, dan FFmpeg/FFprobe. Simpan binaan Windows yt-dlp rasmi sebagai `bin/yt-dlp.exe`. Jalankan dari akar repositori.

```powershell
python -m pip install pyinstaller
python -m PyInstaller --onefile --windowed --name "CLIP SHORT Studio" --add-data "bin/yt-dlp.exe:." clip_short.pyw
```

Fail aplikasi dihasilkan dalam folder `dist`. Binaan sedia guna tersedia pada halaman Releases di GitHub.
