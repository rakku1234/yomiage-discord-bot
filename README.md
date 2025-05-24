# discord読み上げbot

discord.pyを利用しています

## 使用している合成音声エンジン
- [AquesTalk1](https://www.a-quest.com/products/aquestalk_1.html)
- [AquesTalk2](https://www.a-quest.com/products/aquestalk_2.html)
- [AqKanji2Koe](https://www.a-quest.com/products/aqkanji2koe.html)
- [VoiceVox](https://voicevox.hiroshiba.jp/)
- [AivisSpeech](https://aivis-project.com/)

合成音声エンジン、ボイスキャラクターの利用規約に従って使用してください

デフォルトではvoicevoxを使用します

## 必要なソフトウェア
- [uv](https://github.com/astral-sh/uv)
- [FFmpeg](https://ffmpeg.org/)
- [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/ja/visual-cpp-build-tools/)(windowsのみ)

## インストール方法

```
uv sync
```

https://github.com/VOICEVOX/voicevox_core/releases
からダウンローダを使って、voicevoxフォルダに必要なファイルを入れてください

ダウンローダを使わずにvoicevoxフォルダに必要なファイルの入れ方

- [lib(voicevox_core)](https://github.com/VOICEVOX/voicevox_core)
- [onnxruntime](https://github.com/VOICEVOX/onnxruntime-builder)
- [models(vvm)](https://github.com/VOICEVOX/voicevox_vvm)
- [dict(open_jtalk)](https://github.com/r9y9/open_jtalk)

`config-example.json`から`config.json`に名前を変更し、
tokenにdiscord botのトークンを入れる

### 起動方法

```
uv run main.py
```
