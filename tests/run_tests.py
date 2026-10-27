"""nlm-automodder の CLI を自作の小さな譜面（tests/maps.py）で動かし、決まった結果が出るかを確かめる。

使い方:
  python tests/run_tests.py <nlm-automodder.exe>                  確かめる（失敗があれば終了コード 1）
  python tests/run_tests.py <nlm-automodder.exe> --update-golden  tests/golden/ の「結果の一覧」を書き直す

確かめる物は2つ:
  1. 決まった結果（EXPECT）: 例えば視界ブロックのノーツは Warning・ボムは Error、壁よけ 3 回は Warning・4 回は Error。
     AutoModder の判定のしかたが変わった時に気づくための物。
  2. 結果の一覧（tests/golden/<譜面>.json）: 全部の結果と信号機の欄。上流（AutoModder・解析の部品）の版を上げた時は
     --update-golden で書き直し、git diff で何が変わったかを読む（AutoModder接続の調査.md の 1.5 の 2.）。
"""
import json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import maps  # noqa: E402

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

GOLDEN = os.path.join(HERE, 'golden')


def run(exe, req, raw=None):
    data = raw if raw is not None else json.dumps(req).encode('utf-8')
    t = time.perf_counter()
    p = subprocess.run([exe], input=data, capture_output=True, timeout=300)
    dt = time.perf_counter() - t
    out = json.loads(p.stdout.decode('utf-8'))
    return p.returncode, out, dt, p.stderr.decode('utf-8', 'replace')


def ensure(cond, what):
    if not cond:
        raise AssertionError(what)


def find(out, name, severity=None, difficulty='ExpertPlus'):
    return [r for r in out['results'] if r['name'] == name and (severity is None or r['severity'] == severity)
            and r['difficulty'] == difficulty]


def objs(r):
    return [(o['type'], o['beat'], o['x'], o['y']) for o in r['objects']]


def crit(out, d='ExpertPlus', c='Standard'):
    return out['criteria']['diff'][c][d]


# ---- 決まった結果 ----

def e_basic(out):
    assert out['ok'] and out['errors'] == [], out['errors']
    assert out['automodder']['version'] == '1.6.6' and out['config'] == 'default'
    e = crit(out)
    assert e['skipped'] is None and e['notes'] > 20 and e['highest'] == 'Success', e
    assert all(v == 'Success' for v in e['crit'].values()), e['crit']
    bad = [(r['name'], r['severity']) for r in out['results'] if r['severity'] in ('Error', 'Warning')]
    assert not bad, bad
    st = find(out, 'Statistical Data', 'Data')
    assert len(st) == 1 and {'Pass', 'Tech', 'EBPM', 'PEBPM', 'SPS', 'Handness', 'Duration'} <= set(st[0]['data']), st
    # 曲の情報の結果（Difficulty が null）。BPM は AutoModder では常に Inconclusive
    assert [r['severity'] for r in out['results'] if r['name'] == 'BPM' and r['difficulty'] is None] == ['Inconclusive']
    assert out['criteria']['info']['BPM'] == 'Warning' and out['criteria']['info']['Preview'] == 'Success'


def e_hot_start(out):
    r = find(out, 'Hot Start', 'Error')
    assert len(r) == 1 and objs(r[0]) == [('note', 1, 1, 0)], r
    assert r[0]['data'] == {'CurrentBeat': '1', 'MinimumBeat': '3'}, r[0]['data']
    assert crit(out)['crit']['HotStart'] == 'Fail'


def e_vb_note(out):
    r = find(out, 'Vision Block')
    assert [(x['severity'], objs(x)) for x in r] == [('Warning', [('note', 31.25, 1, 2)])], r
    assert r[0]['data']['currentReactionTime'] == '125', r[0]['data']
    # AutoModder の式: (750-300)·e^(-Pass/7.6 - Tech·0.06) + 325 ms（Pass は総合の★ではなく Pass）
    st = find(out, 'Statistical Data', 'Data')[0]['data']
    import math
    want = (750 - 300) * math.exp(-float(st['Pass']) / 7.6 - float(st['Tech']) * 0.06) + 325
    assert abs(int(r[0]['data']['targetReactionTime']) - want) < 3, (r[0]['data'], want)
    assert crit(out)['crit']['VisionBlock'] == 'Warning'   # ノーツの視界ブロックは Warning 止まり


def e_vb_bomb(out):
    r = find(out, 'Vision Block')
    assert [(x['severity'], objs(x)) for x in r] == [('Error', [('bomb', 51.25, 1, 0)])], r
    assert r[0]['data'] == {'currentReactionTime': '125', 'targetReactionTime': '200'}, r[0]['data']
    assert r[0]['objects'][0]['color'] is None
    assert crit(out)['crit']['VisionBlock'] == 'Fail'      # ボムの視界ブロックは Error


def e_short_wall(out):
    r = find(out, 'Wall Length', 'Error')
    assert len(r) == 1 and objs(r[0]) == [('wall', 71, 0, 0)], r
    o = r[0]['objects'][0]
    assert (o['duration'], o['w'], o['h']) == (0.01, 1, 1), o
    assert r[0]['data'] == {'CurrentLength': '0.01', 'MinimumLength': '0.0276'}, r[0]['data']
    assert crit(out)['crit']['Wall'] == 'Fail'


def e_dodge(out):
    r = find(out, 'Wall Dodge')
    got = sorted((x['severity'], objs(x)[0][1], x['data']['CurrentDodgeAmount']) for x in r)
    assert got == [('Error', 95.5, '4'), ('Warning', 90.2, '3'), ('Warning', 95, '3')], got
    assert crit(out)['crit']['Wall'] == 'Fail'


def e_info_warn(out):
    info = [(r['name'], r['severity']) for r in out['results'] if r['difficulty'] is None]
    assert ('Song Name', 'Error') in info and ('Creator', 'Warning') in info and ('Song Preview', 'Suggestion') in info, info
    ci = out['criteria']['info']
    assert (ci['SubName'], ci['Creator'], ci['Preview']) == ('Fail', 'Warning', 'Warning'), ci
    sn = [r for r in out['results'] if r['name'] == 'Song Name' and r['severity'] == 'Error'][0]
    assert sn['data'] == {'SongName': 'NLM test feat. Someone', 'Tags': 'feat.'}, sn['data']


def e_ordering(out):
    r = [x for x in out['results'] if x['name'] == 'Difficulty Ordering']
    assert len(r) == 1 and r[0]['severity'] == 'Error', r
    assert out['criteria']['info']['DifficultyOrdering'] == 'Fail'
    assert set(out['criteria']['diff']) == {'Standard'} and set(out['criteria']['diff']['Standard']) == {'Hard', 'Expert'}
    assert not [x for x in out['results'] if x['characteristic'] not in (None, 'Standard')]
    h = find(out, 'Statistical Data', 'Data', 'Hard')[0]['data']
    e = find(out, 'Statistical Data', 'Data', 'Expert')[0]['data']
    assert float(h['Pass']) > float(e['Pass']), (h, e)


def e_few_notes(out):
    assert out['ok'] and out['errors'] == []
    h = crit(out, 'Hard')
    assert (h['skipped'], h['crit'], h['notes']) == ('notLoaded', None, None), h
    e = crit(out)
    assert e['skipped'] == 'tooFewNotes' and e['notes'] == 10, e
    assert all(v == 'Fail' for v in e['crit'].values()), e['crit']      # 上流は確かめずに全部 Fail の欄を返す
    assert not [x for x in out['results'] if x['difficulty'] is not None]


EXPECT = {'basic': e_basic, 'hot_start': e_hot_start, 'vb_note': e_vb_note, 'vb_bomb': e_vb_bomb, 'short_wall': e_short_wall,
          'dodge': e_dodge, 'info_warn': e_info_warn, 'ordering': e_ordering, 'few_notes': e_few_notes}


def golden_of(out):
    """結果の一覧として残す物（時間・プラグインの版など毎回・版ごとに変わる物は除く）。"""
    return {'automodder': out['automodder'], 'results': out['results'], 'criteria': out['criteria'], 'errors': out['errors']}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    update = '--update-golden' in sys.argv
    if not args:
        sys.exit(__doc__)
    exe = os.path.abspath(args[0])
    fails, times = [], []

    def check(label, fn):
        try:
            fn()
            print('  OK  ', label)
        except Exception as e:
            fails.append(label)
            print('  FAIL', label, '--', type(e).__name__, str(e)[:800])

    print('決まった結果:')
    outs = {}
    for name, fn in EXPECT.items():
        code, out, dt, err = run(exe, maps.request(maps.MAPS[name]()))
        times.append(dt)
        outs[name] = out
        def one(name=name, fn=fn, code=code, out=out, err=err):
            ensure(code == 0, f'exit {code} {err[:300]}')
            fn(out)
        check(f'{name} ({dt:.2f}s)', one)

    print('失敗の時の形:')
    code, out, _, _ = run(exe, maps.request(maps.MAPS['bad_dat']()))
    check('読めない .dat → ok:false・ファイル名', lambda: ensure(code == 1 and out['ok'] is False and 'ExpertPlusStandard.dat' in out['error']['message'], out))
    code2, out2, _, _ = run(exe, None, raw=b'not json')
    check('JSON でない入力 → ok:false', lambda: ensure(code2 == 1 and out2['ok'] is False and out2['error']['type'] == 'InvalidDataException', out2))
    req = maps.request(maps.MAPS['basic']())
    req['protocol'] = 999
    code3, out3, _, _ = run(exe, req)
    check('知らない protocol → ok:false', lambda: ensure(code3 == 1 and 'protocol' in out3['error']['message'], out3))
    req = maps.request(maps.MAPS['basic']())
    del req['songLength']
    code4, out4, _, _ = run(exe, req)
    check('songLength が無い → ok:false', lambda: ensure(code4 == 1 and 'songLength' in out4['error']['message'], out4))
    p = subprocess.run([exe, '--version'], capture_output=True)
    v = json.loads(p.stdout.decode('utf-8'))
    check('--version', lambda: ensure(v['protocol'] == 1 and v['automodder'] == '1.6.6', v))

    print('結果の一覧（tests/golden）:')
    os.makedirs(GOLDEN, exist_ok=True)
    for name, out in outs.items():
        path = os.path.join(GOLDEN, name + '.json')
        g = golden_of(out)
        text = json.dumps(g, ensure_ascii=False, indent=1) + '\n'
        if update or not os.path.exists(path):
            with open(path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(text)
            print('  書いた', os.path.relpath(path, os.path.dirname(HERE)))
            continue
        with open(path, encoding='utf-8') as f:
            old = json.load(f)
        def same():
            if old != g:
                a = {(r['difficulty'], r['name'], r['severity'], json.dumps(r['objects']), json.dumps(r['data'])) for r in old['results']}
                b = {(r['difficulty'], r['name'], r['severity'], json.dumps(r['objects']), json.dumps(r['data'])) for r in g['results']}
                raise AssertionError(f'結果の一覧が変わった（無くなった {len(a - b)}・増えた {len(b - a)}・信号機の欄 '
                                     f'{"同じ" if old["criteria"] == g["criteria"] else "違う"}）: 無くなった例 {sorted(a - b)[:2]} 増えた例 {sorted(b - a)[:2]}'
                                     ' → 意図どおりなら --update-golden で書き直して git diff tests/golden を読む')
        check(name, same)

    print(f'\n1 回の実行: 平均 {sum(times) / len(times):.2f}s・最大 {max(times):.2f}s')
    if fails:
        print(f'失敗 {len(fails)}: {fails}')
        sys.exit(1)
    print('すべて OK')


if __name__ == '__main__':
    main()
