"""Keep exact ignore entries for local files larger than 99 decimal MB."""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[5]
THRESHOLD_BYTES = 99_000_000

def main():
    tracked = set(subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0'))
    rows = []
    for parent, directories, files in os.walk(ROOT):
        directories[:] = [name for name in directories if name not in ('.git', '__pycache__')]
        for name in files:
            path = Path(parent)/name
            if path.is_symlink():
                continue
            size = path.stat().st_size
            if size > THRESHOLD_BYTES:
                relative = path.relative_to(ROOT).as_posix()
                rows.append(dict(path=relative, bytes=size, tracked=relative in tracked))
    ignore = ROOT/'.gitignore'
    content = ignore.read_text()
    lines = set(content.splitlines())
    additions = ['/'+row['path'] for row in sorted(rows, key=lambda item:item['path']) if '/'+row['path'] not in lines]
    if additions:
        ignore.write_text(content.rstrip()+'\n\n# Additional exact files exceeding 99 MB.\n'+'\n'.join(additions)+'\n')
    for row in rows:
        result = subprocess.run(['git', 'check-ignore', '--no-index', '-q', '--', row['path']], cwd=ROOT)
        row['ignored'] = result.returncode == 0
        row['exact_pattern_present'] = '/'+row['path'] in ignore.read_text().splitlines()
    result = dict(threshold_bytes=THRESHOLD_BYTES, files=sorted(rows,key=lambda row:row['path']),
                  added_patterns=additions, verified=all(row['ignored'] and row['exact_pattern_present'] and not row['tracked'] for row in rows),
                  data_deleted=False, whole_result_directories_ignored=False)
    Path(__file__).with_name('large_files_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({key:value for key,value in result.items() if key not in ('files','added_patterns')},indent=2))
    return 0 if result['verified'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
