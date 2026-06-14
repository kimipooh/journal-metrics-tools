# Phase 3D: 実 SEALIB DB read-only 検証タスク

## 目的

Phase 3B/3C で実装した `adapters/sealib.py` と `fetch-journal --adapter sealib` を、実 SEALIB SQLite DB に対して read-only で検証する。

## 対象 DB

- `../../sealib/seas-3.3.1/admin/sqlite_library_seas_ext.db`
- `../../sealib/seas-3.3.1/admin/sqlite_library_seas.db`

前提:

- 2つの DB は同一構造。
- `sqlite_library_seas_ext.db` は拡張版。
- `sqlite_library_seas.db` はコアジャーナル選定版。
- 今回は ext DB を優先検証し、必要に応じて core DB も確認する。

## 制約

- DB 書き込み禁止。
- 検証は SQLite URI `mode=ro` の read-only 接続のみで行う。
- 本番データ投入は行わない。
- `metrics_excel.py` は変更しない。
- 可能ならコード変更なしで検証する。
- 必要な修正が見つかった場合は、修正前に報告する。

## 必ず読むファイル

- `adapters/sealib.py`
- `journal_metrics.py`
- `README.md`
- `docs/adapter-contract.md`

## 検証項目

1. DB ファイルの存在確認。
2. 両 DB の `header` テーブル構造を read-only で確認。
3. `adapters.sealib.fetch_journal()` を使った ext DB 検証。
   - `db_path` 指定で `adapter_error` にならないこと。
   - 既存の誌名らしき query で `fetched` または `multiple_candidates` が返ること。
   - 存在しない query で `not_found` が返ること。
   - candidate が adapter contract の全フィールドを持つこと。
   - DB が read-only 接続で開かれていること。
4. 可能なら core DB でも同じ query を試し、ext DB との差を簡単に確認。
5. `fetch-journal --adapter sealib` を使い、検証用テンプレート xlsx に少数テスト行だけ投入して動作確認。
   - 本番データは投入しない。
   - `journal` シート追記。
   - `main.status` 更新。
   - 2回目実行で追記されないこと。
6. 検証後、検証用 workbook が git 管理外にあることを確認。

## 実行方針

- 実 DB には SELECT のみを実行する。
- workbook は `/tmp` 配下に作成し、リポジトリ内の `journal_metrics.xlsx` は作成・更新しない。
- 検証結果は最終報告で要約する。

## Suggested Commit Message

```text
docs: add Phase 3D SEALIB read-only verification task
```
