"""nlm-automodder の配布物を作る。

  python build.py            → dist/nlm-automodder-<版>-win-x64.zip と dist/manifest.json

手順: submodule が固定コミットのままか・src/Program.cs の AutoModder の版と同じかを確かめる
→ 空のフォルダへ自己完結・win-x64・TrimMode=partial で発行 → 不要物(.pdb/.xml/.lib)を除く
→ ライセンス類と plugin.json を入れる → ビルドした PC のパスが入っていないかを調べる → 簡単な動作確認 → zip と manifest。
manifest.json は GitHub Releases に zip と一緒に添付する。NLM はこれを読んで版・protocol を判定し、
zip の SHA-256 を照合してから展開する（nlm-rating と同じ形）。

版番号は src/Program.cs の Version が唯一の定義元。
"""
import hashlib, json, os, re, shutil, subprocess, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'
RID = 'win-x64'
AM = ROOT / 'external' / 'ChroMapper-AutoModder'
PARTS = {  # 名前 → (submodule の場所, Program.cs の定数名)
    'ChroMapper-AutoModder': (AM, 'AutoModderCommit'),
    'beatleader-analyzer': (AM / 'SubModule' / 'beatleader-analyzer', 'AnalyzerCommit'),
    'beatleader-parser': (AM / 'SubModule' / 'beatleader-analyzer' / 'Parser', 'ParserCommit'),
    'JoshaParity': (AM / 'SubModule' / 'JoshaParity', 'JoshaParityCommit'),
}

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')


def run(cmd, **kw):
    print('>', ' '.join(str(c) for c in cmd))
    return subprocess.run(cmd, check=True, **kw)


def git(*args, cwd=ROOT):
    return subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True, encoding='utf-8').stdout.strip()


def read_consts():
    src = (ROOT / 'src' / 'Program.cs').read_text(encoding='utf-8')
    get = lambda name: re.search(r'public const (?:string|int) %s = "?([^";]+)"?;' % name, src).group(1)
    return {k: get(k) for k in ('Version', 'Protocol', 'AutoModderVersion', 'AutoModderCommit', 'AnalyzerCommit', 'ParserCommit', 'JoshaParityCommit')}


def upstream_commits(c):
    st = git('submodule', 'status', '--recursive')
    bad = [l for l in st.splitlines() if l[:1] in '+-U']
    if bad:
        sys.exit('submodule が固定コミットとずれているか、初期化されていません（git submodule update --init --recursive で戻すか、進めたなら git add してから）:\n' + '\n'.join(bad))
    ups = {}
    for name, (path, const) in PARTS.items():
        head = git('rev-parse', 'HEAD', cwd=path)
        if head != c[const]:
            sys.exit(f'{name} の版が src/Program.cs の {const} と違います: submodule {head} / Program.cs {c[const]}\n'
                     '（上流を進めたなら Program.cs の定数も直す）')
        ups[name] = head
    am_ver = json.loads((AM / 'ChroMapper-LightModding' / 'manifest.json').read_text(encoding='utf-8-sig'))['version']
    if am_ver.lstrip('v') != c['AutoModderVersion']:
        sys.exit(f'AutoModder の版が違います: manifest.json {am_ver} / Program.cs {c["AutoModderVersion"]}')
    return ups


def check_no_local_paths(pub):
    """配る物にビルドした PC のパス（リポジトリの場所・ユーザーのフォルダ）が入っていないかを調べる。"""
    needles = {str(ROOT), str(ROOT).replace('\\', '/'), str(Path.home()), str(Path.home()).replace('\\', '/')}
    pats = []
    for s in needles:
        pats.append(s.encode('utf-8'))
        pats.append(s.encode('utf-16-le'))
    hits = []
    for f in sorted(pub.rglob('*')):
        if not f.is_file():
            continue
        data = f.read_bytes()
        low = data.lower()
        for p in pats:
            if p.lower() in low:
                hits.append(f'{f.relative_to(pub)}: {p[:60]!r}')
    if hits:
        sys.exit('配る物にビルドした PC のパスが入っています:\n' + '\n'.join(hits))
    print('パスの確認 OK（%d ファイル）' % sum(1 for f in pub.rglob('*') if f.is_file()))


def runtime_pack(pub):
    """発行に使った .NET の実行環境の入れ物（NuGet のキャッシュの中）。版は deps.json から読む。"""
    deps = (pub / 'nlm-automodder.deps.json').read_text(encoding='utf-8')
    ver = re.search(r'"runtimepack\.Microsoft\.NETCore\.App\.Runtime\.%s/([^"]+)"' % re.escape(RID), deps).group(1)
    root =Path(os.environ.get('NUGET_PACKAGES', Path.home() / '.nuget' / 'packages')) / f'microsoft.netcore.app.runtime.{RID}' / ver
    if not root.is_dir():
        sys.exit(f'.NET の実行環境の入れ物が見つかりません: {root}')
    return root


def copy_notices(pub):
    """ライセンス類を入れ、配る dll のうち .NET 以外の物が THIRD_PARTY_NOTICES.txt に全部書いてあるかを確かめる。"""
    shutil.copy(ROOT / 'LICENSE', pub / 'LICENSE.txt')
    shutil.copy(ROOT / 'THIRD_PARTY_NOTICES.txt', pub / 'THIRD_PARTY_NOTICES.txt')
    rp = runtime_pack(pub)
    shutil.copy(rp / 'THIRD-PARTY-NOTICES.TXT', pub / 'DOTNET_THIRD_PARTY_NOTICES.txt')
    from_runtime = {f.name.lower() for f in rp.rglob('*') if f.is_file()}
    notices = (ROOT / 'THIRD_PARTY_NOTICES.txt').read_text(encoding='utf-8')
    missing = [f.name for f in pub.iterdir() if f.suffix.lower() in ('.dll', '.exe') and f.name.lower() not in from_runtime
               and not f.name.startswith('nlm-automodder.') and f.name not in notices]
    if missing:
        sys.exit('THIRD_PARTY_NOTICES.txt に書いていない部品があります（中身を確かめて書き足す）: ' + ', '.join(missing))


def smoke_test(exe):
    """自作の小さな譜面で確かめられることだけ見る（決まった結果の確かめは tests/run_tests.py）。"""
    sys.path.insert(0, str(ROOT / 'tests'))
    import maps
    req = maps.request(maps.MAPS['basic']())
    p = subprocess.run([str(exe)], input=json.dumps(req).encode('utf-8'), capture_output=True, timeout=120)
    out = json.loads(p.stdout.decode('utf-8'))
    assert p.returncode == 0 and out['ok'] and not out['errors'], out
    names = {r['name'] for r in out['results']}
    assert {'Statistical Data', 'Vision Block', 'Hot Start'} <= names, names
    print('動作確認 OK  結果 %d 件（%dms）' % (len(out['results']), out['elapsedMs']))


def main():
    c = read_consts()
    ver, proto = c['Version'], int(c['Protocol'])
    if not re.fullmatch(r'\d+\.\d+\.\d+', ver):
        sys.exit(f'版番号の形式が不正です: {ver}')
    ups = upstream_commits(c)
    name = f'nlm-automodder-{ver}-{RID}'
    pub = ROOT / 'out' / name
    shutil.rmtree(pub, ignore_errors=True)   # 上書き発行すると古いファイルが残って起動しない exe ができることがある
    shutil.rmtree(ROOT / 'build', ignore_errors=True)   # obj/bin（Directory.Build.props でここにまとめている）
    run(['dotnet', 'publish', str(ROOT / 'src' / 'NlmAutoModder.csproj'), '-c', 'Release', '-r', RID, '--self-contained', 'true',
         '-p:NlmTrim=partial', '-o', str(pub)])
    for f in list(pub.iterdir()):
        if f.suffix.lower() in ('.pdb', '.xml', '.lib'):
            f.unlink()
    copy_notices(pub)
    meta = {'name': 'nlm-automodder', 'version': ver, 'protocol': proto, 'platform': RID, 'exe': 'nlm-automodder.exe',
            'automodder': c['AutoModderVersion'], 'upstream': ups}
    (pub / 'plugin.json').write_text(json.dumps(meta, indent=1), encoding='utf-8')

    check_no_local_paths(pub)
    smoke_test(pub / 'nlm-automodder.exe')

    DIST.mkdir(exist_ok=True)
    zpath = DIST / f'{name}.zip'
    zpath.unlink(missing_ok=True)
    # zip の直下にファイルを置く（NLM が plugins/automodder/<版>/ へそのまま展開する）。区切りは '/'
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(pub.rglob('*')):
            if f.is_file():
                z.write(f, f.relative_to(pub).as_posix())
    data = zpath.read_bytes()
    manifest = {**meta, 'zip': {'name': zpath.name, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}}
    (DIST / 'manifest.json').write_text(json.dumps(manifest, indent=1), encoding='utf-8')
    print(f'\n{zpath}  {len(data) / 1e6:.1f}MB\n{DIST / "manifest.json"}')
    print('展開後のサイズ: %.1fMB' % (sum(f.stat().st_size for f in pub.rglob('*') if f.is_file()) / 1e6))


if __name__ == '__main__':
    main()
