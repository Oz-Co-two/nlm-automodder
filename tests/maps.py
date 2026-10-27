"""テスト用の小さな譜面（自作・v3）を作る。他人の譜面は使わない。

どの譜面も同じ土台（BPM 120・曲の長さ 75 秒＝150 拍・NJS 16）に、確かめたい物だけを足す。
土台は、赤（x=1）と青（x=2）を一番下の段に毎拍置き、下・上を交互に振る単純な物。
確かめたい物を入れる所（WINDOWS の拍の範囲）には土台のノーツを置かない。
"""
import json

BPM = 120
SONG_LENGTH = 75.0          # 秒（＝150 拍）
NOTES_FROM, NOTES_TO = 8, 136   # 土台のノーツの拍（136 拍＝68 秒。曲の終わりまで 2 秒以上空ける）
WINDOWS = [(30, 36), (50, 56), (70, 76), (88, 100)]   # 確かめたい物を入れる所（土台のノーツを置かない）


def in_window(b):
    return any(a <= b < z for a, z in WINDOWS)


def note(b, x, y, c, d, a=0):
    return {'b': b, 'x': x, 'y': y, 'c': c, 'd': d, 'a': a}


def bomb(b, x, y):
    return {'b': b, 'x': x, 'y': y}


def wall(b, x, y, d, w, h):
    return {'b': b, 'x': x, 'y': y, 'd': d, 'w': w, 'h': h}


def base_notes(dense=False):
    """毎拍（dense なら半拍ごと）に赤 x=1・青 x=2 を一番下の段へ。向きは 1 つごとに下・上を交互。"""
    step = 0.5 if dense else 1
    out = []
    k = 0
    while (b := NOTES_FROM + k * step) <= NOTES_TO:
        if not in_window(b):
            d = 1 if k % 2 == 0 else 0      # 1=下 0=上
            out += [note(b, 1, 0, 0, d), note(b, 2, 0, 1, d)]
        k += 1
    return out


def lights():
    # 種類 0〜4 のライトを半拍ごとに点ける（曲の長さ 150 拍に 300 個＝1 拍あたり 2 個。AutoModder の既定は 1 拍あたり 1 個以上）
    return [{'b': i * 0.5, 'et': i % 5, 'i': 1, 'f': 1} for i in range(int(SONG_LENGTH * BPM / 60 * 2))]


def diff_v3(notes, bombs=(), walls=(), chains=(), arcs=()):
    key = lambda o: o['b']
    return {
        'version': '3.3.0', 'bpmEvents': [], 'rotationEvents': [],
        'colorNotes': sorted(notes, key=key), 'bombNotes': sorted(bombs, key=key), 'obstacles': sorted(walls, key=key),
        'sliders': list(arcs), 'burstSliders': list(chains), 'waypoints': [],
        'basicBeatmapEvents': lights(), 'colorBoostBeatmapEvents': [],
        'lightColorEventBoxGroups': [], 'lightRotationEventBoxGroups': [], 'lightTranslationEventBoxGroups': [],
        'basicEventTypesWithKeywords': {}, 'useNormalEventsAsCompatibleEvents': True,
    }


def info_v2(diffs, song='NLM test', sub='', author='Oz', mapper='Oz', preview=(20.0, 10.0), extra_sets=()):
    """diffs: [(difficulty, rank, filename, njs)]"""
    return {
        '_version': '2.1.0', '_songName': song, '_songSubName': sub, '_songAuthorName': author, '_levelAuthorName': mapper,
        '_beatsPerMinute': BPM, '_shuffle': 0, '_shufflePeriod': 0, '_previewStartTime': preview[0], '_previewDuration': preview[1],
        '_songFilename': 'song.egg', '_coverImageFilename': 'cover.png', '_environmentName': 'DefaultEnvironment',
        '_allDirectionsEnvironmentName': 'GlassDesertEnvironment', '_songTimeOffset': 0,
        '_difficultyBeatmapSets': [{'_beatmapCharacteristicName': 'Standard', '_difficultyBeatmaps': [
            {'_difficulty': d, '_difficultyRank': r, '_beatmapFilename': f, '_noteJumpMovementSpeed': njs, '_noteJumpStartBeatOffset': 0}
            for d, r, f, njs in diffs]}] + list(extra_sets),
    }


def one(dat, **info_kw):
    """Standard の ExpertPlus 1 つだけの譜面。"""
    return {'info': info_v2([('ExpertPlus', 9, 'ExpertPlusStandard.dat', 16)], **info_kw), 'files': {'ExpertPlusStandard.dat': dat}}


def request(m, song_length=SONG_LENGTH):
    return {'protocol': 1,
            'info': {'filename': 'Info.dat', 'json': json.dumps(m['info'])},
            'difficulties': [{'filename': k, 'json': v if isinstance(v, str) else json.dumps(v)} for k, v in m['files'].items()],
            'songLength': song_length}


# ---- 確かめる物ごとの譜面 ----

def m_basic():
    return one(diff_v3(base_notes()))


def m_hot_start():
    # 1.5 秒（120 BPM で 3 拍）より前の物 → Hot Start が Error
    return one(diff_v3(base_notes() + [note(1, 1, 0, 0, 0)]))


def m_vb_note():
    # 真ん中の段の真ん中（x=1,y=1）のノーツの 0.25 拍（125ms）後ろに、その陰（x=1,y=2）のノーツ → Vision Block の Warning
    return one(diff_v3(base_notes() + [note(31, 1, 1, 0, 1), note(31.25, 1, 2, 0, 0)]))


def m_vb_bomb():
    # 真ん中（x=1,y=1）の下向きの赤の 0.25 拍後、振り終わりの所（x=1,y=0）にボム → Vision Block の Error（ボム）
    return one(diff_v3(base_notes() + [note(51, 1, 1, 0, 1), note(53, 1, 0, 0, 0)], bombs=[bomb(51.25, 1, 0)]))


def m_short_wall():
    # 13.8ms（120 BPM で 0.0276 拍）より短い壁 → Wall Length が Error
    return one(diff_v3(base_notes(), walls=[wall(71, 0, 0, 0.01, 1, 1)]))


def m_dodge():
    # 頭をよける壁（左＝x0 幅2、右＝x2 幅2、高さ5）を 1 秒（2 拍）の中で左右に切り替える
    #   89〜90.2 拍: 左・右・左 ＝3 回 → Warning（既定 2.5 回以上）
    #   94〜95.5 拍: 左・右・左・右 ＝4 回 → Error（既定 3.5 回以上）。95 拍の壁は 3 回で Warning
    L = lambda b: wall(b, 0, 0, 0.25, 2, 5)
    R = lambda b: wall(b, 2, 0, 0.25, 2, 5)
    return one(diff_v3(base_notes(), walls=[L(89), R(89.6), L(90.2), L(94), R(94.5), L(95), R(95.5)]))


def m_info_warn():
    # 曲名に feat.（サブ名に書く物）→ Song Name が Error、11 文字以上の作者名 → Creator が Warning、試聴が既定の 12/10 → Suggestion
    return one(diff_v3(base_notes()), song='NLM test feat. Someone', mapper='AVeryLongMapperName', preview=(12, 10))


def m_ordering():
    # Hard（ノーツが倍）の方が Expert より Pass が高い → Difficulty Ordering が Error
    # OneSaber の難易度は AutoModder が確かめない（criteria にも results にも出ない）
    info = info_v2([('Hard', 5, 'HardStandard.dat', 16), ('Expert', 7, 'ExpertStandard.dat', 16)],
                   extra_sets=[{'_beatmapCharacteristicName': 'OneSaber', '_difficultyBeatmaps': [
                       {'_difficulty': 'Expert', '_difficultyRank': 7, '_beatmapFilename': 'ExpertOneSaber.dat',
                        '_noteJumpMovementSpeed': 16, '_noteJumpStartBeatOffset': 0}]}])
    return {'info': info, 'files': {
        'HardStandard.dat': diff_v3(base_notes(dense=True)),
        'ExpertStandard.dat': diff_v3(base_notes()),
        'ExpertOneSaber.dat': diff_v3([n for n in base_notes() if n['c'] == 1]),
    }}


def m_few_notes():
    # ノーツ 20 未満の難易度は AutoModder が確かめない（信号機の欄は全部 Fail のまま・結果なし）
    # Hard の .dat は渡さない（notLoaded）
    info = info_v2([('Hard', 5, 'HardStandard.dat', 16), ('ExpertPlus', 9, 'ExpertPlusStandard.dat', 16)])
    return {'info': info, 'files': {'ExpertPlusStandard.dat': diff_v3(base_notes()[:10])}}


def m_bad_dat():
    # 読めない .dat（JSON でない）→ ok:false でファイル名を返す
    return {'info': info_v2([('ExpertPlus', 9, 'ExpertPlusStandard.dat', 16)]), 'files': {'ExpertPlusStandard.dat': '{"version":"3.3.0","colorNotes":[{'}}


MAPS = {
    'basic': m_basic, 'hot_start': m_hot_start, 'vb_note': m_vb_note, 'vb_bomb': m_vb_bomb, 'short_wall': m_short_wall,
    'dodge': m_dodge, 'info_warn': m_info_warn, 'ordering': m_ordering, 'few_notes': m_few_notes, 'bad_dat': m_bad_dat,
}
