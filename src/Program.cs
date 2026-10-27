// nlm-automodder CLI
//   AutoModder（LightAi39/ChroMapper-AutoModder）の自動の確かめ（BLMapCheck）を、改変せずそのまま動かす。
//   標準入力: {"protocol":1, "info":{"filename":"Info.dat","json":"..."},
//             "difficulties":[{"filename":"ExpertPlusStandard.dat","json":"..."}], "songLength":123.4}
//   標準出力: {"protocol":1, "ok":true, "plugin":{...}, "automodder":{...}, "config":"default",
//             "results":[...], "criteria":{"info":{...}, "diff":{...}}, "errors":[...]}
//   失敗時:   {"protocol":1, "ok":false, "error":{"type":"...","message":"..."}}（終了コード 1）
//
// 確かめ方は AutoModder の画面（ChroMapper-LightModding の AutocheckHelper）と同じ順:
//   1. 曲の情報（Info）の確かめ = BLMapChecker.CheckSongInfo()
//   2. Standard の各難易度 = BLMapChecker.CheckSingleDifficulty(characteristic, difficulty, rank)
//      AutoModder の画面は難易度を確かめる前にその難易度の .dat を読み直すので、ここでも難易度ごとに読み直す。
//   設定は AutoModder の既定の設定（Configs/Config.cs の初期値）。上流は確かめの途中で設定の SliderPrecision を
//   書き換え、次に確かめる難易度にまで持ち越す（AutoModder では確かめる順で結果が変わり得る）。ここでは毎回既定の設定に
//   戻してから確かめる＝「ChroMapper を起動して最初にその難易度を確かめた時」と同じ結果。
using System.Diagnostics;
using System.Diagnostics.CodeAnalysis;
using System.Reflection;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using beatleader_parser;
using BLMapCheck;
using BLMapCheck.BeatmapScanner.Data.Criteria;
using BLMapCheck.Classes.Results;
using BLMapCheck.Configs;
using Parser.Map.Difficulty.V3.Base;
using Parser.Map.Difficulty.V3.Event;
using Parser.Map.Difficulty.V3.Grid;

namespace NlmAutoModder
{
    public static class Program
    {
        public const int Protocol = 1;
        public const string Version = "0.1.0";   // 版番号の唯一の定義元（build.py がここを読む）

        // 動かしている AutoModder の版（build.py が submodule の固定コミット・manifest.json と同じかを確かめる）
        public const string AutoModderVersion = "1.6.6";
        public const string AutoModderCommit = "0c2621507170c427506297457c8abdef7765dad1";
        public const string AnalyzerCommit = "078615b7f99c38c96bb33261e19894572b22851e";
        public const string ParserCommit = "aa9a24da419afd5aa210c365d9b3d65a19593d7e";
        public const string JoshaParityCommit = "6a88301558d69691a80dcdd5dc4768152a6c4362";

        // AutoModder の画面が自動の確かめのボタンを出すのは Standard の難易度だけ
        const string CheckedCharacteristic = "Standard";

        public static int Main(string[] args)
        {
            var stdout = new StreamWriter(Console.OpenStandardOutput(), new UTF8Encoding(false)) { AutoFlush = true };
            // 上流は例外を Console.WriteLine で出すので、標準出力（結果の JSON 専用）に混ざらないよう標準エラーへ回す
            Console.SetOut(Console.Error);
            if (args.Length > 0 && args[0] == "--version")
            {
                stdout.Write(new JsonObject
                {
                    ["protocol"] = Protocol,
                    ["version"] = Version,
                    ["automodder"] = AutoModderVersion,
                }.ToJsonString());
                return 0;
            }
            try
            {
                string input;
                using (var r = new StreamReader(Console.OpenStandardInput(), new UTF8Encoding(false)))
                    input = r.ReadToEnd();
                JsonObject req;
                try { req = JsonNode.Parse(input)?.AsObject() ?? throw new InvalidDataException("empty input"); }
                catch (JsonException e) { throw new InvalidDataException("input is not JSON: " + e.Message); }
                stdout.Write(Run(req).ToJsonString());
                return 0;
            }
            catch (Exception e)
            {
                stdout.Write(new JsonObject
                {
                    ["protocol"] = Protocol,
                    ["ok"] = false,
                    ["plugin"] = PluginInfo(),
                    ["error"] = ErrorInfo(e),
                }.ToJsonString());
                return 1;
            }
        }

        static JsonObject PluginInfo() => new() { ["name"] = "nlm-automodder", ["version"] = Version };

        static JsonObject AutoModderInfo() => new()
        {
            ["version"] = AutoModderVersion,
            ["commit"] = AutoModderCommit,
            ["parts"] = new JsonObject
            {
                ["beatleader-analyzer"] = AnalyzerCommit,
                ["beatleader-parser"] = ParserCommit,
                ["JoshaParity"] = JoshaParityCommit,
            },
        };

        static JsonObject ErrorInfo(Exception e)
        {
            var j = new JsonObject { ["type"] = e.GetType().Name, ["message"] = e.Message };
            // どの確かめで落ちたかの手がかり（落ちたメソッドの名前。配る物にデバッグ情報は無いので、ファイルのパスは出ない）
            var first = e.StackTrace?.Split('\n').Select(l => l.Trim()).FirstOrDefault(l => l.Length > 0);
            if (first != null) j["where"] = first.StartsWith("at ") ? first[3..] : first;
            return j;
        }

        static string Str(JsonNode n, string what)
        {
            if (n is JsonValue v && v.TryGetValue<string>(out var s)) return s;
            throw new InvalidDataException($"{what} must be a string");
        }

        static (string filename, string json) FileOf(JsonNode n, string what)
        {
            if (n is not JsonObject o) throw new InvalidDataException($"{what} must be an object {{filename, json}}");
            return (Str(o["filename"], what + ".filename"), Str(o["json"], what + ".json"));
        }

        static JsonObject Run(JsonObject req)
        {
            var sw = Stopwatch.StartNew();
            int proto = req["protocol"] is JsonValue pv && pv.TryGetValue<int>(out var p) ? p : 0;
            if (proto != Protocol) throw new InvalidDataException($"unsupported protocol {proto} (expected {Protocol})");

            var info = FileOf(req["info"], "info");
            // 上流の読み込みは名前が info.dat（大文字小文字を問わない）のファイルを Info として探す
            if (!info.filename.Equals("info.dat", StringComparison.OrdinalIgnoreCase)) info.filename = "Info.dat";
            var files = new List<(string filename, string json)> { info };
            if (req["difficulties"] is JsonArray diffs)
            {
                for (int i = 0; i < diffs.Count; i++)
                {
                    var f = FileOf(diffs[i], $"difficulties[{i}]");
                    if (f.filename.Equals("info.dat", StringComparison.OrdinalIgnoreCase))
                        throw new InvalidDataException($"difficulties[{i}] must not be Info.dat");
                    files.Add(f);
                }
            }
            else if (req["difficulties"] != null) throw new InvalidDataException("difficulties must be an array");

            // 曲の長さ（秒）。上流は ColdEnd・Outside・Lights で使う（0 だと Lights がエラーを出す）。必ず渡してもらう
            if (req["songLength"] is not JsonValue lv || !lv.TryGetValue<double>(out var songLengthD) || !(songLengthD > 0) || double.IsInfinity(songLengthD))
                throw new InvalidDataException("songLength (seconds, > 0) is required");
            float songLength = (float)songLengthD;

            // 読み込めるかを先に確かめる（上流の読み込みは失敗の理由を捨てて null を返すので、どのファイルかだけでも分かるようにする）
            CheckLoadable(files, songLength);

            var checker = new BLMapChecker();
            var results = new JsonArray();
            var errors = new JsonArray();
            JsonObject infoCrit = null;

            // 1. 曲の情報の確かめ
            checker.LoadMap(files, songLength);
            var info0 = BLMapChecker.map.Info;
            var loaded = BLMapChecker.map.Difficulties.Select(x => (x.Characteristic, x.Difficulty, notes: x.Data.Notes.Count)).ToList();
            try
            {
                Config.Instance.Reset();
                var r = checker.CheckSongInfo();
                foreach (var x in r.Results) results.Add((JsonNode)ResultJson(x));
                infoCrit = CritJson(r.InfoCriteriaResult);
            }
            catch (Exception e)
            {
                var ej = ErrorInfo(e);
                ej["stage"] = "info";
                errors.Add((JsonNode)ej);
            }

            // 2. Standard の各難易度の確かめ（Info.dat に書かれた順）
            var diffCrit = new JsonObject();
            foreach (var set in info0._difficultyBeatmapSets ?? new())
            {
                if (set._beatmapCharacteristicName != CheckedCharacteristic) continue;
                var byDiff = diffCrit[set._beatmapCharacteristicName] as JsonObject;
                if (byDiff == null) diffCrit[set._beatmapCharacteristicName] = byDiff = new JsonObject();
                foreach (var bm in set._difficultyBeatmaps ?? new())
                {
                    string c = set._beatmapCharacteristicName, d = bm._difficulty;
                    int rank = bm._difficultyRank;
                    var entry = new JsonObject { ["difficultyRank"] = rank, ["filename"] = bm._beatmapFilename };
                    byDiff[d] = entry;
                    int li = loaded.FindIndex(x => x.Characteristic == c && x.Difficulty == d);
                    if (li < 0)
                    {
                        // .dat が渡されていない（上流の読み込みは黙って飛ばす）。AutoModder なら確かめの途中で落ちる所
                        entry["notes"] = null;
                        entry["skipped"] = "notLoaded";
                        entry["highest"] = null;
                        entry["crit"] = null;
                        continue;
                    }
                    int notes = loaded[li].notes;
                    entry["notes"] = notes;
                    // 上流はノーツ 20 未満の難易度を確かめず、信号機の欄が全部 Fail の空の結果を返す（それもそのまま出す）
                    entry["skipped"] = notes < 20 ? "tooFewNotes" : null;
                    try
                    {
                        checker.LoadMap(files, songLength);   // AutoModder の画面と同じく、確かめる前に読み直す
                        Config.Instance.Reset();
                        var r = checker.CheckSingleDifficulty(c, d, rank);
                        foreach (var x in r.Results) results.Add((JsonNode)ResultJson(x));
                        var crit = r.DifficultyCriteriaResults.FirstOrDefault(x => x.Characteristic == c && x.Difficulty == d)?.Crit;
                        entry["highest"] = crit == null ? null : crit.HighestSeverityCheck().ToString();
                        entry["crit"] = CritJson(crit);
                    }
                    catch (Exception e)
                    {
                        entry["highest"] = null;
                        entry["crit"] = null;
                        entry["error"] = true;
                        var ej = ErrorInfo(e);
                        ej["stage"] = "difficulty";
                        ej["characteristic"] = c;
                        ej["difficulty"] = d;
                        errors.Add((JsonNode)ej);
                    }
                }
            }

            return new JsonObject
            {
                ["protocol"] = Protocol,
                ["ok"] = true,
                ["plugin"] = PluginInfo(),
                ["automodder"] = AutoModderInfo(),
                ["config"] = "default",
                ["songLength"] = songLengthD,
                ["elapsedMs"] = sw.ElapsedMilliseconds,
                ["results"] = results,
                ["criteria"] = new JsonObject { ["info"] = infoCrit, ["diff"] = diffCrit },
                ["errors"] = errors,
            };
        }

        static void CheckLoadable(List<(string filename, string json)> files, float songLength)
        {
            var parser = new Parse();
            if (parser.TryLoadString(files, songLength) != null) return;
            if (parser.TryLoadString(new() { files[0] }, songLength) == null)
                throw new InvalidDataException("Info.dat could not be read by beatleader-parser");
            var bad = new List<string>();
            for (int i = 1; i < files.Count; i++)
                if (parser.TryLoadString(new() { files[0], files[i] }, songLength) == null) bad.Add(files[i].filename);
            throw new InvalidDataException("map could not be read by beatleader-parser" + (bad.Count > 0 ? ": " + string.Join(", ", bad) : ""));
        }

        // 信号機の欄（InfoCrit / DiffCrit の CritResult の項目を全部）。上流が項目を足しても自動で出る
        static JsonObject CritJson<[DynamicallyAccessedMembers(DynamicallyAccessedMemberTypes.PublicProperties)] T>(T crit) where T : class
        {
            if (crit == null) return null;
            var j = new JsonObject();
            foreach (var pi in typeof(T).GetProperties(BindingFlags.Public | BindingFlags.Instance))
                if (pi.PropertyType == typeof(InfoCrit.CritResult)) j[pi.Name] = pi.GetValue(crit).ToString();
            return j;
        }

        static JsonObject ResultJson(CheckResult x)
        {
            var objs = new JsonArray();
            foreach (var o in x.BeatmapObjects ?? new()) objs.Add((JsonNode)ObjectJson(o));
            return new JsonObject
            {
                ["name"] = x.Name,
                ["characteristic"] = x.Characteristic,
                ["difficulty"] = x.Difficulty,
                ["difficultyRank"] = x.Difficulty == null ? null : x.difficultyRank,
                ["severity"] = x.Severity.ToString(),
                ["checkType"] = x.CheckType,
                ["description"] = x.Description,
                ["objects"] = objs,
                ["data"] = DataJson(x.ResultData),
            };
        }

        // ResultData（キーと値の並び・値は文字）。同じキーが2回以上あれば、そのキーの値は文字の配列にする（落とさないため）
        static JsonObject DataJson(List<BLMapCheck.Classes.Results.KeyValuePair> data)
        {
            var j = new JsonObject();
            foreach (var kv in data ?? new())
            {
                var key = kv.Key ?? "";
                if (!j.ContainsKey(key)) { j[key] = kv.Value; continue; }
                if (j[key] is JsonArray a) a.Add((JsonNode)JsonValue.Create(kv.Value));
                else
                {
                    var prev = j[key]?.GetValue<string>();
                    j[key] = new JsonArray(JsonValue.Create(prev), JsonValue.Create(kv.Value));
                }
            }
            return j;
        }

        // 結果に付いている物（ノーツ・ボム・壁・チェーン・アーク・ライト）。拍は譜面ファイルの拍（b）そのまま
        static JsonObject ObjectJson(BeatmapObject o)
        {
            var j = new JsonObject
            {
                ["type"] = o switch
                {
                    Note => "note",
                    Bomb => "bomb",
                    Chain => "chain",
                    Arc => "arc",
                    Wall => "wall",
                    Light => "light",
                    _ => o.GetType().Name,
                },
                ["beat"] = o.Beats,
                ["x"] = o is BeatmapGridObject g0 ? g0.x : null,
                ["y"] = o is BeatmapGridObject g1 ? g1.y : null,
                ["color"] = o is BeatmapColorGridObject c0 ? c0.Color : null,
                ["seconds"] = o.Seconds,
            };
            switch (o)
            {
                case Note n:
                    j["d"] = n.CutDirection;
                    j["a"] = n.AngleOffset;
                    break;
                case Chain c:
                    j["d"] = c.CutDirection;
                    j["tb"] = c.TailInBeats;
                    j["tx"] = c.tx;
                    j["ty"] = c.ty;
                    j["sc"] = c.SliceCount;
                    j["s"] = c.Squish;
                    break;
                case Arc a:
                    j["d"] = a.CutDirection;
                    j["tb"] = a.TailInBeats;
                    j["tx"] = a.tx;
                    j["ty"] = a.ty;
                    j["tc"] = a.TailCutDirection;
                    j["mu"] = a.Multiplier;
                    j["tmu"] = a.TailMultiplier;
                    j["m"] = a.AnchorMode;
                    break;
                case Wall w:
                    j["duration"] = w.DurationInBeats;
                    j["w"] = w.Width;
                    j["h"] = w.Height;
                    break;
                case Light l:
                    j["et"] = l.Type;
                    j["i"] = l.Value;
                    j["f"] = l.f;
                    break;
            }
            return j;
        }
    }
}
