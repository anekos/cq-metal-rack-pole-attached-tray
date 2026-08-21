# CLAUDE.md

CadQuery のパラメトリックモデルを uv + click で CLI 化したプロジェクト
(`~/forge/cad/CadQuery/` 共通のテンプレート構成)。

## セットアップ

作業を始めるときは最初に一度だけ実行する。

```bash
make setup   # uv sync + pre-commit install
```

## コマンド

```bash
uv run pole-attached-tray build              # dist/ に STL を出力
uv run pole-attached-tray build --help       # Param の各フィールドがそのままオプション
uv run pole-attached-tray build out.stl      # 出力先は位置引数
make build                             # ソース変更を監視して再ビルド (axe)
```

- `dist/` は CWD 相対に作られるので、必ずプロジェクトルートで実行する。
- `--show` は `cadquery.vis.show` で GUI を開く。**非対話の作業では使わないこと。**

## 構成

- `src/pole_attached_tray/main.py` — pydantic の `Param` と `build(param) -> cq.Workplane`。
  `build()` は純粋関数にする (ファイル I/O や表示を持ち込まない)。
- `src/pole_attached_tray/__init__.py` — click の CLI。`@define_options(Param)` が
  `Param` のフィールドを `--field-name` オプションに変換し、`output` / `param` / `show`
  を関数に渡す。
- 変わりうる寸法はすべて `Param` のフィールドにする (`build()` の中に数値を直書きしない)。
  `Field(..., description=...)` を書くと `--help` に出る。
- 単位は mm と度。

### `define_options` の型の扱い

- `Literal["a", "b"]` → `click.Choice`。
- `X | None` → `X` を取るオプション (未指定なら `None`)。それ以外の Union は `TypeError`。
- `bool` はフラグではなく値を取る (`--tab true`)。

## モデルを変えたら

1. `uv run pole_attached_tray build` を通す。
2. `val().Volume()` と `val().BoundingBox()` を手計算のざっくり見積もりと突き合わせる。
   はめあいや隙間を変えたときは `section(z)` の外形も測って、狙った寸法か確認する。
3. OCCT の例外はその操作に対して形状が不正だという合図 (フィレット半径が大きすぎる、
   シェルが自己交差する等)。盲目的に再実行せずパラメータを見直す。
4. 極端な値 (薄い / 小さい / 大きい) でも `isValid()` になるか一通り試す。

## コミット前

```bash
uv run mypy src && uv run ruff format src && uv run ruff check src
```

- `filename` が使う `version_number()` は git のコミット数を読むので、
  リポジトリには最低 1 つコミットが必要。
- `dist/` と `.venv/` はコミットしない (`.gitignore` 済み)。
