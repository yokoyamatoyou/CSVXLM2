# CSVからMHLW XMLへの変換・パッケージツール (CSVXLM)

## 概要

本プロジェクトは「特定健診／特定保健指導」データのCSVを入力とし、設定ファイルに基づきXMLへ変換、ZIP形式でパッケージ化するツールです。

## ディレクトリ構成

- `src/` メインのPythonコード
- `config_rules/` 各種設定JSONおよびルールファイル
- `data/` 入力CSV、生成されたXML、ZIPアーカイブ、XSDスキーマを格納
- `tests/` 単体テスト
- `CSVからXML変換詳細手順説明_utf8.txt` 変換手順のUTF-8版（Shift_JIS版は`CSVからXML変換詳細手順説明.txt`）

## 環境構築

Python 3.10以上で動作します。依存パッケージをインストールするには以下を実行してください。

```bash
pip install -r requirements.txt
```

XSDファイルはプロジェクト直下の `XSD/` または `5521111111_00280081_202405271_1/XSD/` に配置してください。
検証に必要なXSDはこの1セットだけで十分です。ルールブックとして扱ってください。

## 使い方

### GUI（日本語対応）

```bash
python src/gui.py
```

画面はすべて日本語表示となっており、設定JSONとCSVプロファイルを指定して変換を実行します。
Windows環境ではプロジェクトルートの `run_gui.bat` を実行することで同じGUIが起動します。

### CLI

```bash
python src/main.py [-c CONFIG] [-p PROFILE] [--log-level LEVEL]
```
モジュール形式で実行する場合:
```bash
python -m csv_to_xml_converter [-c CONFIG] [-p PROFILE] [--log-level LEVEL]
```

- `CONFIG` : 設定JSONへのパス (デフォルト: `config_rules/config.json`)
- `PROFILE` : CSVプロファイル名 (デフォルト: `grouped_checkup_profile`)
- `LEVEL` : ログレベル (`DEBUG`, `INFO` など)
- `--sample-test` : テスト用フォルダからCSVを処理します。 `--sample-num-files` で各フォルダから処理するファイル数を指定できます (デフォルト2)。 `--sample-only` を併用するとこの簡易テストのみを実行します。
- ユーザーはCSVファイルだけを用意すれば十分です。変換時にJSONが自動生成されるため、JSONファイルをアップロードしたり手動で変換したりする必要はありません。
- `data/input_csvs/` 配下に複数のCSVファイルを置くことで、一度の実行で全ファイルを変換できます。
- CSVからXMLへ変換する際、各CSVの解析結果は`.json`ファイルとして自動保存されます。デフォルトではCSVと同じ場所に出力されますが、設定ファイルの`paths.json_output_dir`を指定すると別ディレクトリに保存できます。

出力XMLは`data/output_xmls/`、ZIPアーカイブは`data/output_archives/`に生成されます。
テスト用にはリポジトリ直下に `TEST.csv` を同梱しています。以前の README で案内していた
`3610123279`、`3610123675`、`3610123808`、`40歳未満健診CSV` といったフォルダは
現在は含まれていません。`TEST.csv` を利用して設定ファイルの入力パスを変更するか、
`data/input_csvs/` 配下に配置して簡易的な動作確認を行ってください。

## テスト実行

依存パッケージをインストール後、プロジェクトルートで次を実行してテストを行います。

```bash
pytest -q
```

## ライセンス

このプロジェクトはMITライセンスです。
