from pathlib import Path
import hashlib, json, shutil, struct, subprocess, sys, uuid, os
from inputs import check_inputs, input_files
import lz4.block
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'switch files'
KEYS = SOURCE/'prod.keys'
TOOL_SOURCE = ROOT/'tools/hacpack.exe'
STAGE = None
TITLE = 0x0100E04C554D0000
OLD = 0x0100000011D90000
MOD = ROOT/'Luminescent mod'
SUPPORTED = json.loads((ROOT/'builder/supported-inputs.json').read_text(encoding='utf-8'))
sha = lambda b: hashlib.sha256(b).hexdigest()

def require(condition, message):
    if not condition: raise ValueError(message)

def filehash(p):
    with p.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()

def unpack_nso(path):
    b=path.read_bytes(); require(b[:4]==b'NSO0', 'Invalid NSO')
    h=bytearray(b[:256]); flags=struct.unpack_from('<I',h,12)[0]
    image=bytearray(); segments=[]
    for i in range(3):
        off,va,n=struct.unpack_from('<III',h,16+16*i)
        cn=struct.unpack_from('<I',h,96+4*i)[0]
        d=lz4.block.decompress(b[off:off+cn],uncompressed_size=n) if flags&(1<<i) else b[off:off+n]
        require(len(d)==n and hashlib.sha256(d).digest()==h[160+32*i:192+32*i],f'Invalid NSO segment {i}: {path.name}')
        require(va>=len(image),'Overlapping NSO segments')
        image.extend(bytes(va-len(image)));image.extend(d);segments.append((va,n))
    return h,image,segments

def read_ips(path):
    b=path.read_bytes();require(b[:5]==b'IPS32','Expected IPS32')
    p=5; records=[]
    while b[p:p+4]!=b'EEOF':
        require(p+6<=len(b),'Truncated patch')
        off=int.from_bytes(b[p:p+4],'big');n=int.from_bytes(b[p+4:p+6],'big');p+=6
        if n:
            d=b[p:p+n];p+=n;require(len(d)==n,'Truncated patch record')
        else:
            n=int.from_bytes(b[p:p+2],'big');d=b[p+2:p+3]*n;p+=3
            require(len(d)==n,'Truncated patch run')
        records.append((off,d))
    require(p+4==len(b),'Unexpected IPS trailer')
    return records

def prepare():
    check_inputs(ROOT, SUPPORTED)
    require(shutil.disk_usage(ROOT).free >= 30*1024**3, 'At least 30 GiB of free space is required for the build and verification.')
    for layer in SUPPORTED['layers'].values():
        require(all(len(str(STAGE/'romfs'/rel)) < 240 for rel in layer), 'The build path is too long. Extract the pack to a short folder such as C:\\LPBuilder.')
    available={line.split('=',1)[0].strip() for line in KEYS.read_text(encoding='utf-8-sig').splitlines() if '=' in line}
    require({'header_key','key_area_key_application_00'}<=available,'Required key names missing; key values are never printed')
    for d in ['romfs','exefs','control','logo','ncas','result','notices']: (STAGE/d).mkdir(parents=True,exist_ok=True)
    shutil.copyfile(TOOL_SOURCE,STAGE/'hacpack.exe')
    print('Staging the 1.3.0 game assets and Luminescent overlay...',flush=True)
    files={};sources={}
    for layer,folder in [('game',SOURCE/'romfs'),('luminescent',MOD/'romfs')]:
        for p in input_files(folder):
            rel=p.relative_to(folder)
            if layer=='luminescent' and rel.as_posix() in ['README.md','LICENSE.txt']:
                shutil.copyfile(p,STAGE/'notices'/p.name);continue
            key=rel.as_posix();q=STAGE/'romfs'/rel;q.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(p,q)
            record={'size':p.stat().st_size,'sha256':filehash(q)}
            require(record==SUPPORTED['layers'][layer][key], 'Unsupported or changed '+layer+' asset: '+key)
            files[key]={**record,'layer':layer}
            if len(files)%2000==0: print(f'  {len(files):,} merged asset paths prepared...',flush=True)
    print(f'Staged {len(files):,} final asset files.',flush=True)
    for name in ['main','main.npdm','rtld','sdk','subsdk0']:
        p=SOURCE/'exefs'/name;shutil.copyfile(p,STAGE/'exefs'/name);sources['exefs/'+name]=filehash(p)
    h,image,segments=unpack_nso(SOURCE/'exefs/main')
    require(h[64:80].hex().upper()=='94CEAE325C205C4B9D6F7235552F28FD','Wrong game build ID')
    ips=MOD/'exefs/94CEAE325C205C4B9D6F7235552F28FD.ips';records=read_ips(ips)
    require(len(records)==155,'Unexpected patch count')
    for off,d in records:
        pos=off-0x100
        require(any(va<=pos and pos+len(d)<=va+n for va,n in segments),'Patch outside NSO segments')
        image[pos:pos+len(d)]=d
    new_id=hashlib.sha256(b'Luminescent Platinum 2.2F standalone\0'+image).digest()
    # A unique build ID isolates the baked main from BD-targeted runtime IPS patches.
    h[64:96]=new_id;struct.pack_into('<I',h,0x1c,0x100);struct.pack_into('<I',h,0x2c,0)
    struct.pack_into('<I',h,12,struct.unpack_from('<I',h,12)[0]|0x3f)
    out=bytearray(h)
    for i,(va,n) in enumerate(segments):
        d=bytes(image[va:va+n]);compressed=lz4.block.compress(d,store_size=False)
        struct.pack_into('<III',out,16+16*i,len(out),va,n)
        struct.pack_into('<I',out,96+4*i,len(compressed))
        out[160+32*i:192+32*i]=hashlib.sha256(d).digest();out.extend(compressed)
    (STAGE/'exefs/main').write_bytes(out)
    _,check,checksegments=unpack_nso(STAGE/'exefs/main')
    require(check==image and checksegments==segments,'Patched NSO did not round trip')
    for off,d in records: require(check[off-0x100:off-0x100+len(d)]==d,'Patch byte mismatch')
    shutil.copyfile(MOD/'exefs/subsdk1',STAGE/'exefs/subsdk1')
    _,module,_=unpack_nso(STAGE/'exefs/subsdk1')
    require(bytes.fromhex('94CEAE325C205C4B9D6F7235552F28FD') not in module,'Module contains original build ID: review before changing it')
    for name in ['LICENSE','NOTICE']:
        if (MOD/'exefs'/name).is_file(): shutil.copyfile(MOD/'exefs'/name,STAGE/'notices'/('exefs-'+name))
    for p in MOD.glob('*Changelog*'):
        if p.is_file():shutil.copyfile(p,STAGE/'notices'/p.name)
    n=bytearray((STAGE/'exefs/main.npdm').read_bytes())
    require(n[:4]==b'META','Invalid NPDM');aci=struct.unpack_from('<I',n,0x70)[0];acid=struct.unpack_from('<I',n,0x78)[0]
    require(struct.unpack_from('<Q',n,aci+0x10)[0]==OLD,'Unexpected program ID')
    n[0x20:0x30]=b'LuminescentPlt'.ljust(16,b'\0')
    struct.pack_into('<Q',n,aci+0x10,TITLE);struct.pack_into('<QQ',n,acid+0x210,TITLE,TITLE)
    # Preserve explicit permissions for reading other Pokemon saves (bonus rewards).
    # This dump has no old BD ID in its FS access-control descriptor.
    fsa_off,fsa_size=struct.unpack_from('<II',n,aci+0x20)
    require(struct.pack('<Q',OLD) not in n[aci+fsa_off:aci+fsa_off+fsa_size],'Unexpected BD save grant: review required')
    (STAGE/'exefs/main.npdm').write_bytes(n)
    ctl=SOURCE/'control 0';n=bytearray((ctl/'control.nacp').read_bytes())
    require(n[0x3060:0x3070].split(b'\0')[0]==b'1.3.0','Wrong control version')
    for i in range(16):
        n[i*0x300:i*0x300+0x200]='Pokémon Luminescent Platinum'.encode().ljust(0x200,b'\0')
        n[i*0x300+0x200:(i+1)*0x300]=b'Team Luminescent'.ljust(0x100,b'\0')
    n[0x3060:0x3070]=b'2.2F'.ljust(16,b'\0')
    for off,value in [(0x3038,TITLE),(0x3070,TITLE+0x1000),(0x3078,TITLE),(0x30f8,TITLE)]:struct.pack_into('<Q',n,off,value)
    # LocalCommunicationId is a network permission list, not save ownership.
    # Preserve it so game networking constants still have their expected grants.
    (STAGE/'control/control.nacp').write_bytes(n)
    icons=[p for p in (ROOT/'Homescreen Icon').iterdir() if p.is_file() and p.suffix.lower() in ['.png','.jpg','.jpeg','.webp','.bmp']]
    if icons:
        with Image.open(icons[0]) as im:
            im.load()
            if im.mode=='RGBA' or 'transparency' in im.info:
                rgba=im.convert('RGBA');bg=Image.new('RGBA',rgba.size,'#171923');bg.alpha_composite(rgba);im=bg.convert('RGB')
            else: im=im.convert('RGB')
            im.resize((256,256),Image.Resampling.LANCZOS).save(STAGE/'control/icon.jpg','JPEG',quality=95,subsampling=0)
    else:
        im=Image.new('RGB',(256,256),'#171923');draw=ImageDraw.Draw(im)
        draw.polygon([(128,18),(218,112),(128,202),(38,112)],fill='#a9aab4',outline='#efe5b3',width=5)
        draw.text((128,110),'LP',anchor='mm',font_size=70,fill='#171923')
        draw.text((128,233),'LUMINESCENT',anchor='mm',font_size=21,fill='#f4f1e7')
        im.save(STAGE/'control/icon.jpg','JPEG',quality=95,subsampling=0)
    jpeg=(STAGE/'control/icon.jpg').read_bytes();require(len(jpeg)<128*1024,'Icon exceeds 128 KiB')
    languages=['AmericanEnglish','BritishEnglish','Japanese','French','German','LatinAmericanSpanish','Spanish','Italian','Dutch','CanadianFrench','Portuguese','Russian','Korean','TraditionalChinese','SimplifiedChinese','BrazilianPortuguese']
    flags=struct.unpack_from('<I',n,0x302c)[0]
    for i,language in enumerate(languages):
        if flags&(1<<i): (STAGE/'control'/('icon_'+language+'.dat')).write_bytes(jpeg)
    require(flags&1,'American English icon is required')
    (STAGE/'control/icon.jpg').unlink()
    for name in ['NintendoLogo.png','StartupMovie.gif']:shutil.copyfile(SOURCE/'logo'/name,STAGE/'logo'/name)
    manifest={'title':'Pokémon Luminescent Platinum','title_id':f'{TITLE:016X}','title_version':0,'display_version':'2.2F',
      'base_version':'1.3.0 (supported input fingerprints matched)','original_build_id':'94CEAE325C205C4B9D6F7235552F28FD','main_build_id':new_id.hex(),
      'ips_records':len(records),'ips_sha256':filehash(ips),'game_assets':files,'source_exefs':sources,
      'staged_exefs':{p.name:filehash(p) for p in (STAGE/'exefs').iterdir()},
      'control':{p.name:filehash(p) for p in (STAGE/'control').iterdir()},
      'logo':{p.name:filehash(p) for p in (STAGE/'logo').iterdir()},
      'runtime_status':'Reproduces the previously user-confirmed working build; each newly built package still needs a launch/save check'}
    shutil.copyfile(STAGE/'exefs/main.npdm',STAGE/'npdm-before-pack.bin')
    (STAGE/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Executable patches, identity, save owner, and icons prepared.',flush=True)

def package():
    require((STAGE/'manifest.json').is_file(),'Run preparation first')
    tool=STAGE/'hacpack.exe'
    def run(args):
        cmd=[str(tool),'-k',str(KEYS),'--titleid',f'{TITLE:016X}','--tempdir',str(STAGE/'temp'),'--backupdir',str(STAGE/'backup')]+list(map(str,args))
        with (STAGE/'build.log').open('a',encoding='utf-8') as log:
            result=subprocess.run(cmd,cwd=STAGE,stdout=log,stderr=subprocess.STDOUT)
        require(result.returncode==0,'Packaging failed. See '+str(STAGE/'build.log'))
    def nca(args):
        before=set((STAGE/'ncas').glob('*.nca'))
        run(['--type','nca','-o',STAGE/'ncas']+args)
        fresh=set((STAGE/'ncas').glob('*.nca'))-before
        require(len(fresh)==1,'Expected one new NCA');return fresh.pop()
    require(not list((STAGE/'ncas').iterdir()),'NCA output is not empty')
    print('Building Program archive...',flush=True)
    program=nca(['--ncatype','program','--exefsdir',STAGE/'exefs','--romfsdir',STAGE/'romfs','--logodir',STAGE/'logo'])
    print('Building Control archive...',flush=True)
    control=nca(['--ncatype','control','--romfsdir',STAGE/'control'])
    print('Building Application metadata...',flush=True)
    nca(['--ncatype','meta','--titletype','application','--programnca',program,'--controlnca',control,'--titleversion','00000000'])
    print('Packing NSP...',flush=True)
    run(['--type','nsp','--ncadir',STAGE/'ncas','-o',STAGE/'result'])
    require((STAGE/'result'/f'{TITLE:016x}.nsp').is_file(),'NSP output missing')
    print('Package built; independent verification is next.',flush=True)

def publish_release(stage,dest,nsp):
    """Publish the NSP last; restore the previous release if a move fails."""
    sources={'verification.json':stage/'verification.json','build-record.json':stage/'build-record.json',
             'Pokemon_Luminescent_Platinum.nsp':nsp}
    backup=stage/'previous-release';backup.mkdir()
    moved=[];published=[]
    try:
        for name in sources:
            target=dest/name
            if target.exists():
                require(target.is_file(),'Release output is not a file: '+name)
                os.replace(target,backup/name);moved.append(name)
        for name,source in sources.items():
            os.replace(source,dest/name);published.append(name)
    except BaseException:
        failures=[]
        for name in reversed(published):
            try:os.replace(dest/name,stage/('unpublished-'+name))
            except OSError:failures.append(name)
        for name in reversed(moved):
            try:os.replace(backup/name,dest/name)
            except OSError:failures.append(name)
        if failures:raise OSError('Publishing stopped and rollback was incomplete. Previous files are in '+str(backup)+'. Check these files: '+', '.join(failures))
        raise

def main():
    global STAGE
    (ROOT/'.build').mkdir(exist_ok=True)
    lock=ROOT/'.build/build.lock'
    try: fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError: raise ValueError('Another build may be running. If no builder is open, remove .build/build.lock and try again.')
    try:
        with os.fdopen(fd,'w') as f:f.write(str(os.getpid()))
        STAGE=ROOT/'.build'/('run-'+uuid.uuid4().hex[:10])
        prepare();package()
        print('Verifying the finished NSP and every game asset...',flush=True)
        result=subprocess.run([sys.executable,str(ROOT/'builder/verify_package.py'),'--stage',str(STAGE),'--keys',str(KEYS),'--out',str(STAGE/'verification.json')],capture_output=True,text=True,encoding='utf-8',errors='replace')
        with (STAGE/'build.log').open('a',encoding='utf-8') as log:log.write(result.stdout+result.stderr)
        require(result.returncode==0,'Verification failed. The previous Release was kept. See '+str(STAGE/'build.log'))
        verification=json.loads((STAGE/'verification.json').read_text(encoding='utf-8'))
        require(verification['result']=='PASS','Verification did not pass')
        # Check source executable/control/mod inputs again before publishing the result.
        for rel,digest in SUPPORTED['small_files'].items():require(filehash(ROOT/rel)==digest,'An input changed during the build: '+rel)
        dest=ROOT/'Release';dest.mkdir(exist_ok=True)
        record={k:v for k,v in verification.items() if k!='checks'}
        record.update(builder_version='1.0.0',source_game='Brilliant Diamond 1.3.0',source_mod='Luminescent Platinum 2.2F BD',icon='custom' if any(p.is_file() and p.suffix.lower() in ['.png','.jpg','.jpeg','.webp','.bmp'] for p in (ROOT/'Homescreen Icon').iterdir()) else 'generated LP emblem')
        (STAGE/'build-record.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
        nsp=STAGE/'result'/f'{TITLE:016x}.nsp'
        publish_release(STAGE,dest,nsp)
        print('\nDone: '+str(dest/'Pokemon_Luminescent_Platinum.nsp'),flush=True)
        print('Verification: PASS. The builder can now be closed.',flush=True)
    finally:
        lock.unlink(missing_ok=True)

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,AssertionError,Image.DecompressionBombError) as error:
        print('\nBUILD FAILED: '+str(error),file=sys.stderr);sys.exit(1)
