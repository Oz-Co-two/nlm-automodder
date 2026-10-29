# nlm-automodder

[Non-Linear Mapper (NLM)](https://github.com/Oz-Co-two/nlm-oz-co2) で作った譜面を、**AutoModder**（BeatLeader のランクの審査で使われる
ChroMapper のプラグイン [LightAi39/ChroMapper-AutoModder](https://github.com/LightAi39/ChroMapper-AutoModder)）の自動の確かめにかけるための
追加プラグインです。AutoModder の確かめの部分（BLMapCheck）を**改変せずに**組み立て、ChroMapper の外で動かします。
NLM 本体には同梱していません。必要な人だけが取り込みます（「難易度を測る」の nlm-rating とは別のプラグインです）。

> **AutoModder・BeatLeader の公式ツールではありません。** 結果は AutoModder v1.6.6 の**既定の設定**で確かめた物です。
> AutoModder の確かめは BeatLeader の今の基準と違う所があります（視界ブロックの時間の式・壁よけの回数・チェーンの長さなど）。
> ランクの審査の結果ではありません。
>
> *This is not an official AutoModder or BeatLeader tool. It runs AutoModder's auto-check (v1.6.6, default settings)
> outside ChroMapper. AutoModder's checks differ from the current BeatLeader criteria in places. Results are not ranking decisions.*

## 使い方

- **必要なもの**: 譜面チェックに「AutoModder」のタブがある NLM（Windows 版）。**このタブは [NLM v2.1.0-oz](https://github.com/Oz-Co-two/nlm-oz-co2/releases/tag/v2.1.0-oz) 以降に入っています。**
  プラグインは Windows（64bit）専用です。.NET のインストールは不要です（同梱しています）。
- **取り込み**: NLM の「譜面チェック（BeatLeader基準）」のパネルの 3 つ目のタブ「AutoModder」を開き、「📥 プラグインを取り込む…」→「GitHub から取り込む」を押します。
  この GitHub Releases から約 12MB をダウンロードし、ファイルが配布元の情報（`manifest.json` の SHA-256・大きさ）と一致することを確かめてから、
  NLM のフォルダの `plugins/automodder/<版>/` に保存します。
- **確かめる**: タブを開くと、書き出すのと同じ内容（Info.dat・各難易度の .dat・書き出す song.egg の長さ）で AutoModder の自動の確かめを動かし、
  結果を曲の情報 → 難易度ごとに、重い順（Unrankable → Questionable → …）に出します。拍をクリックすると、その位置へ移動します。
  - 譜面が前回確かめた時のままなら動かし直しません（「↻ もう一度確かめる」で動かし直せます）。
  - AutoModder は曲の長さを使うので、音源を読み込んでいない時は確かめられません。
- **更新**: タブの「更新を確認」を押した時に GitHub を見に行きます。NLM v2.1.1-oz 以降は、取り込み済みなら NLM の起動時にも確かめ、
  新しい版があれば変更点（[CHANGELOG.md](CHANGELOG.md) の見出し）を出して知らせます（NLM の環境設定「起動時に…確認する」で止められます）。
  古い版は残るので、取り込み済みの版が 2 つ以上あれば、タブの版の選択から元に戻せます。
- **ネットに繋がらない PC で使う**: Releases の zip を展開した中身を、NLM のフォルダの `plugins/automodder/<版>/`（例: `plugins/automodder/0.1.0/`）に置きます。
- **削除**: NLM のフォルダの `plugins/automodder/` を消します。
- **単体で使う**: `nlm-automodder.exe < 入力.json > 結果.json`（入出力は下）。

## AutoModder と同じにするための決めごと

- 確かめの順は AutoModder の画面（`ChroMapper-LightModding/Helpers/AutocheckHelper.cs`）と同じ:
  1. 曲の情報の確かめ（`BLMapChecker.CheckSongInfo()`）
  2. **Standard** の各難易度（`CheckSingleDifficulty(characteristic, difficulty, rank)`・Info.dat に書かれた順）。
     AutoModder の画面に確かめのボタンがあるのは Standard だけなので、他の characteristic（OneSaber など）は確かめません。
     AutoModder の画面は難易度を確かめる前にその .dat を読み直すので、ここでも難易度ごとに読み直します。
- 設定は AutoModder の既定の設定（`BLMapCheck/Configs/Config.cs` の初期値）。**難易度ごとに既定の設定へ戻してから確かめます**。
  上流はスライダーの確かめの途中で設定の `SliderPrecision` を書き換え、次に確かめる難易度にまで持ち越します（AutoModder では
  確かめる順で結果が変わり得る）。ここでの結果は「ChroMapper を起動して、最初にその難易度を確かめた時」と同じです。
- ノーツ 20 未満の難易度は、上流が確かめずに信号機の欄を全部 `Fail` のまま返します。そのまま出し、`skipped: "tooFewNotes"` を付けます。
- 上流の癖もそのままです（直すと AutoModder と結果がずれるため）。例: 「Difficulty Ordering」は★の計算の部品に NJS を速さの倍率として
  渡しているので、`CurrentOrder` の数は Pass の値ではありません（並びの向きだけが意味を持ちます）。
- 数の書き方は地域の設定に左右されません（小数点は「.」）。.NET 10 で動かすので、Unity（ChroMapper）の中で動かした時と、
  文の中の数の桁数・小数の最後の桁がわずかに違うことがあり得ます（判定そのものは同じコード）。

## NLM とのやりとり（protocol 1）

1 回ごとに `nlm-automodder.exe` を起動し、標準入力に JSON を渡して標準出力の JSON を受け取ります（常駐・通信ポートなし）。
NLM は譜面チェックと同じ「書き出す Info.dat（v2）＋各難易度の .dat（v3）」を渡します（上流の読み込みは v2・v4 の .dat も読めます）。

```jsonc
// 標準入力（UTF-8）
{ "protocol": 1,
  "info": { "filename": "Info.dat", "json": "…Info.dat の中身…" },
  "difficulties": [ { "filename": "ExpertPlusStandard.dat", "json": "…" } ],  // Info.dat の _beatmapFilename の名前で
  "songLength": 123.4 }                                                       // 曲の長さ（秒・必須）。書き出す song.egg の長さ

// 標準出力（UTF-8）
{ "protocol": 1, "ok": true,
  "plugin": { "name": "nlm-automodder", "version": "0.1.0" },
  "automodder": { "version": "1.6.6", "commit": "0c26215…",
                  "parts": { "beatleader-analyzer": "078615b…", "beatleader-parser": "aa9a24d…", "JoshaParity": "6a88301…" } },
  "config": "default", "songLength": 123.4, "elapsedMs": 350,
  "results": [
    { "name": "Vision Block", "characteristic": "Standard", "difficulty": "ExpertPlus", "difficultyRank": 9,
      "severity": "Warning", "checkType": "Vision", "description": "Notes must be placed with enough time to react",
      "objects": [ { "type": "note", "beat": 31.25, "x": 1, "y": 2, "color": 0, "seconds": 15.624999, "d": 0, "a": 0 } ],
      "data": { "currentReactionTime": "125", "targetReactionTime": "703" } },
    { "name": "Song Name", "characteristic": null, "difficulty": null, "difficultyRank": null, "severity": "Passed", … } ],
  "criteria": {
    "info": { "SongName": "Success", "SubName": "Success", …, "Preview": "Warning" },
    "diff": { "Standard": { "ExpertPlus": { "difficultyRank": 9, "filename": "ExpertPlusStandard.dat", "notes": 198,
                                            "skipped": null, "highest": "Warning",
                                            "crit": { "HotStart": "Success", "VisionBlock": "Warning", … } } } } },
  "errors": [] }

// 失敗時（入力が読めない・譜面が読めない など）: 終了コード 1
{ "protocol": 1, "ok": false, "plugin": { … }, "error": { "type": "InvalidDataException", "message": "…", "where": "…" } }
```

- `results` は AutoModder の `CheckResult` を全部（`Passed` も）そのまま並べた物。曲の情報の結果は `difficulty` が `null`。
  - `severity`: `Passed` / `Info` / `Suggestion` / `Warning` / `Error` / `Inconclusive` / `Data`（`Data` は「Statistical Data」＝難易度ごとの Pass・Tech・EBPM など）。
    AutoModder の画面では Warning と Inconclusive が「Questionable」、Error が「Unrankable」です。
  - `description` は AutoModder の英語の文そのまま。`data` は `ResultData`（値は文字。同じキーが 2 回以上あれば、そのキーは文字の配列）。
  - `objects` は結果に付いた物。`type` は `note` / `bomb` / `chain` / `arc` / `wall` / `light`。`beat` は**譜面ファイルの拍（b）そのまま**。
    種類ごとに `d`（向き）・`a`、チェーン・アークの `tb`・`tx`・`ty` など、壁の `duration`・`w`・`h` も付けます。
  - 文字はファイル由来の値（曲名など）を含むので、画面に出す時は HTML として扱わないこと（textContent で）。
- `criteria` は AutoModder の信号機の欄（`InfoCrit`・`DiffCrit`）。値は `Success` / `Warning` / `Fail`。`highest` はその難易度の欄で一番重い物
  （AutoModder の画面の印の色）。`skipped`: `tooFewNotes`（上流が確かめない）・`notLoaded`（その .dat が渡されていない。`crit` は `null`）。
- `errors`: 確かめの途中で上流が例外を出した時（`stage`: `info` / `difficulty`）。その難易度は `crit: null`・`error: true` になり、他の難易度は続けます。
  （AutoModder の画面なら確かめが止まる所。途中までの結果は出しません。）
- 上流は例外を `Console.WriteLine` で出すため、標準出力は結果専用にし、それ以外は標準エラーへ回しています。
- `--version` で `{"protocol":1,"version":"0.1.0","automodder":"1.6.6"}` を返します。
- 入出力の形を変える時は `Program.Protocol` を上げます（NLM は自分が知らない protocol のプラグインを入れない、nlm-rating と同じ決まり）。

## 中身

- `external/ChroMapper-AutoModder` — AutoModder を **submodule で固定コミット参照**（コピーも改変もしない）。v1.6.6 = `0c26215`。
  その中の submodule（AutoModder の `.gitmodules` が指す版のまま）:
  - `SubModule/beatleader-analyzer` = BeatLeader/beatleader-analyzer `078615b`（★の Pass/Tech）
    - その中の `Parser` = BeatLeader/beatleader-parser `aa9a24d`（譜面の読み込み）
  - `SubModule/JoshaParity` = Loloppe/JoshaParity `6a88301`（スイングの割り振り・リセット）
- `src/upstream/` — 上流のソースを `<Compile Include>` で取り込む包みの csproj（設定は上流の csproj に合わせる）。上流の csproj を直接使わない理由:
  - `BLMapCheck.csproj`: Analyzer.dll・JoshaParity.dll を上流の obj フォルダの決まった場所から読み、組み立ての後に ChroMapper のフォルダへ xcopy する。
  - `Analyzer.csproj`: net9.0 と netstandard2.1 の 2 つを作り、net10.0 の exe から参照すると net9.0 の方が選ばれる（AutoModder が使うのは netstandard2.1 の方で、
    `#if NETSTANDARD2_0_OR_GREATER` の分岐が違う）。包みは netstandard2.1 だけを作る。
  - `JoshaParity.csproj`: 同梱の古い `dll/Parser.dll` を参照する。JoshaParity `6a88301` のソースはその古い Parser の形で書かれていて新しい Parser では組み立てられないので、
    包みも古い dll で組み立て、出力には写さない（`Private=false`）。実行時は AutoModder と同じく新しい Parser（`aa9a24d`）が読まれる（名前・版が同じ部品）。
  - Parser は上流の `Parser.csproj` をそのまま参照（netstandard2.1 が選ばれる＝AutoModder と同じ）。
- `src/Program.cs` — 自前の CLI（入出力の JSON・確かめの順）。
- `Directory.Build.props` — 配る dll にビルドした PC のパスを入れない（`PathMap`・デバッグ情報なし）。obj/bin を `build/` にまとめる（submodule を汚さない）。
- `tests/` — 自作の小さな譜面での確かめ（下）。
- `build.py` — 配布物（zip と manifest.json）を作る。

## ビルド

.NET SDK 10 以降と Python 3 が必要です。

```
git clone --recurse-submodules https://github.com/Oz-Co-two/nlm-automodder.git
python build.py
```

`dist/` に `nlm-automodder-<版>-win-x64.zip`（約 12MB・展開後 約 29MB）と `manifest.json` ができます。版番号は `src/Program.cs` の `Version` が唯一の定義元です。

- build.py は、submodule が固定コミットのままか・`Program.cs` の AutoModder の版とコミットの定数・AutoModder の `manifest.json` の版が同じかを確かめてから組み立てます。
- 自己完結（.NET 同梱）・win-x64 のみ・`TrimMode=partial`（.NET 本体だけを削り、上流の部品は丸ごと残す。上流はリフレクションを使うので `full` は避ける）。
  事前コンパイル（ReadyToRun）は使っていません（nlm-rating と同じ判断。1 回 0.5 秒ほどで、ほとんどは起動）。
- `PublishTrimmed` はコマンドラインではなく csproj 側で指定します（コマンドラインだと netstandard の部品にも伝わって失敗します）。
- 発行先は毎回空にします（上書きで発行すると、起動しない exe ができることがありました）。
- 配る物の全ファイルを、ビルドした PC のパス（リポジトリの場所・ユーザーのフォルダ）で走査し、見つかれば止まります。
- 配る dll のうち .NET 以外の物が `THIRD_PARTY_NOTICES.txt` に全部書いてあるかを確かめ、.NET の第三者の表示（`DOTNET_THIRD_PARTY_NOTICES.txt`）を入れます。

## テスト

```
python tests/run_tests.py out/nlm-automodder-<版>-win-x64/nlm-automodder.exe
```

- 自作の小さな譜面（`tests/maps.py`・v3・他人の譜面は使わない）で、決まった結果が出るかを確かめます: 視界ブロックのノーツ＝Warning・ボム＝Error、
  13.8ms より短い壁＝Error、1.5 秒より前の物（hot start）＝Error、壁よけ 1 秒に 3 回＝Warning・4 回＝Error（既定 2.5・3.5）、曲名の feat.・長い作者名、
  難易度の並び、ノーツ 20 未満・.dat が無い・読めない .dat・入力の誤り。
- 全部の結果と信号機の欄は `tests/golden/<譜面>.json` に残してあり、違えば失敗します。上流の版を上げた時は `--update-golden` で書き直し、
  `git diff tests/golden` で何が変わったかを読みます。

## リリース

1. `src/Program.cs` の `Version` を上げる（入出力の形を変えたら `Protocol` も）。変更点を `CHANGELOG.md` と `CHANGELOG.en.md` に
   同じ版・同じ数の太字の見出し（`- **〜**`）で書く（`build.py` が manifest.json の `notes` に入れ、NLM の更新のお知らせに出る。合わないと止まる）
2. `python build.py` → `python tests/run_tests.py out/nlm-automodder-<版>-win-x64/nlm-automodder.exe`
3. タグ `v<版>` で GitHub Release を作り、**zip と manifest.json の両方**を添付する。
   NLM は `releases/latest/download/manifest.json` を読み、zip の SHA-256 を照合してから展開します（nlm-rating と同じ）。
   公開した後に変更点の文だけを直す時は、リリースの manifest.json を落として `python build.py notes manifest.json` で作り直し、
   `gh release upload v<版> manifest.json --clobber` で差し替えます（zip の項目は変わらない）。
4. 公開は**プラグインのリリースが先、それを使う NLM の版が後**。

## AutoModder の版が上がった時の追い方

1. AutoModder の新しいリリースのタグとコミットを確かめ、`BLMapCheck/` の差分と、AutoModder の中の submodule（analyzer・parser・JoshaParity）の版を見る。
2. submodule を上げる（中の submodule は AutoModder が指す版に合わせる）:
   ```
   git -C external/ChroMapper-AutoModder fetch --tags
   git -C external/ChroMapper-AutoModder checkout v<新しい版>
   git -C external/ChroMapper-AutoModder submodule update --init --recursive
   ```
   中の submodule に `git submodule update --remote` は使わないでください（AutoModder が指す版から外れます）。
3. `src/Program.cs` の `AutoModderVersion`・`AutoModderCommit`・`AnalyzerCommit`・`ParserCommit`・`JoshaParityCommit` を直す（build.py が照合します）。
4. 上流の `BLMapCheck.csproj`・`Analyzer.csproj`・`JoshaParity.csproj` の設定・部品（PackageReference）が変わっていれば `src/upstream/` の包みも合わせる。
   部品が増えたら `THIRD_PARTY_NOTICES.txt` も直す（build.py が書き漏れを止めます）。入口（`BLMapChecker`）・結果の型（`CheckResult`・`InfoCrit`・`DiffCrit`）が
   変わっていれば `Program.cs` も。
5. `python build.py` → `python tests/run_tests.py … --update-golden` → `git diff tests/golden` で結果の変わり方を読む → `git add external src tests && git commit`。
6. 結果の形（項目・重さの種類・物の種類）が変わった時だけ NLM 側を直す（NLM は知っている項目・値だけを画面へ通すため）。
   新しい確かめの名前は、NLM に訳が無ければ英語のまま出ます。画面に出る AutoModder の版は、プラグインの出力（`automodder.version`）から自動で変わります。

## ライセンス

自前のコードは MIT License（`LICENSE`）。AutoModder・同梱の部品の表示は `THIRD_PARTY_NOTICES.txt` にあります（どれも MIT License）。
AutoModder は Light Ai さん（[LightAi39](https://github.com/LightAi39)）の作品で、確かめの部分（BLMapCheck）は Light Ai さんと Loloppe さんによるものです。
このプラグインは AutoModder のソースを改変せずに組み立てて動かしているだけで、確かめの中身はすべて AutoModder の物です。
