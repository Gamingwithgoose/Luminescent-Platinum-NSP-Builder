"""Standard-library input checks; never prints key material."""
from pathlib import Path
import hashlib,json,struct,sys

FOLDERS=['switch files/exefs','switch files/romfs','switch files/control 0','switch files/logo',
         'Luminescent mod/exefs','Luminescent mod/romfs','Homescreen Icon','Release']
IMAGE_EXTENSIONS={'.png','.jpg','.jpeg','.webp','.bmp'}

def input_files(folder):
    return sorted(p for p in folder.rglob('*') if p.is_file() and p.name!='.gitkeep')

def file_hash(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def require(c,message):
    if not c:raise ValueError(message)

def check_inputs(root,supported):
    missing=[rel for rel in list(supported['small_files'])+['switch files/prod.keys','tools/hacpack.exe'] if not (root/rel).is_file()]
    require(not missing,'Missing files:\n  '+'\n  '.join(missing)+'\nSee README.md, step 3. Keep the exact filenames and avoid extra nested folders.')
    for rel,digest in supported['small_files'].items():
        require(file_hash(root/rel)==digest,'Unsupported or modified input: '+rel+'\nUse Brilliant Diamond 1.3.0 and Luminescent Platinum 2.2F BD. See README.md.')
    require(file_hash(root/'tools/hacpack.exe')==supported['tool_sha256'],'The bundled packager is missing or changed. Extract the full build pack again.')
    keyfile=root/'switch files/prod.keys'
    require(keyfile.stat().st_size<=1024*1024,'The keyset file is unexpectedly large.')
    values={}
    for line in keyfile.read_text(encoding='utf-8-sig').splitlines():
        if '=' in line:
            k,v=line.split('=',1);values[k.strip()]=v.split('#',1)[0].strip()
    for name,length in [('header_key',32),('key_area_key_application_00',16)]:
        value=values.get(name,'')
        valid=len(value)==length*2 and all(c in '0123456789abcdefABCDEF' for c in value)
        require(valid,'prod.keys is missing a valid '+name+'. Key values are never displayed.')
    for layer,folder in [('game',root/'switch files/romfs'),('luminescent',root/'Luminescent mod/romfs')]:
        require(folder.is_dir(),'Missing folder: '+str(folder.relative_to(root)))
        actual={p.relative_to(folder).as_posix() for p in input_files(folder)}
        if layer=='luminescent':actual-={'README.md','LICENSE.txt'}
        expected=set(supported['layers'][layer]);missing=sorted(expected-actual);extra=sorted(actual-expected)
        if missing or extra:
            details=[]
            if missing:details.append(f'{len(missing)} missing files; first paths: '+', '.join(missing[:5]))
            if extra:details.append(f'{len(extra)} unexpected files; first paths: '+', '.join(extra[:5]))
            raise ValueError('Unsupported '+layer+' RomFS layout: '+'; '.join(details)+'.\nCopy the contents of the correct romfs folder, not another enclosing folder. Do not pre-merge the mod.')
    icons=[p for p in (root/'Homescreen Icon').iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS]
    require(len(icons)<=1,'Keep only one image in Homescreen Icon, or leave it empty for the generated LP emblem.')
    # Full asset fingerprints are checked as the build stages each input file.

def main():
    root=Path(__file__).resolve().parents[1]
    for folder in FOLDERS:(root/folder).mkdir(parents=True,exist_ok=True)
    if sys.argv[1:]==['--prepare']:
        print('Input folders are ready. Follow README.md to add your own files.');return
    require(not sys.argv[1:],'Unknown option')
    supported=json.loads((root/'builder/supported-inputs.json').read_text(encoding='utf-8'))
    check_inputs(root,supported);print('Required files and supported versions checked.')

if __name__=='__main__':
    try:main()
    except (ValueError,OSError) as error:
        print('INPUT CHECK FAILED: '+str(error),file=sys.stderr);sys.exit(1)
