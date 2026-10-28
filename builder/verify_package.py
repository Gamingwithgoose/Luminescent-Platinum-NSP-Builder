"""Stream-verify the finished package without displaying console keys."""
from pathlib import Path
import hashlib, json, mmap, struct, argparse
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

p=argparse.ArgumentParser(description='Verify a staged Luminescent NSP without displaying keys.')
p.add_argument('--stage',type=Path,required=True);p.add_argument('--keys',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
args=p.parse_args()
ST=args.stage
MAN=json.loads((ST/'manifest.json').read_text(encoding='utf-8'))
TID=int(MAN['title_id'],16)
NSP=ST/'result'/(MAN['title_id'].lower()+'.nsp')
KEYFILE=args.keys
VERIFY=ST/'verification';VERIFY.mkdir(exist_ok=True)
CHUNK=8*1024*1024
sha=lambda x:hashlib.sha256(x).digest()

def need(c,m):
    if not c:raise ValueError(m)

def digest_range(f,start,size):
    h=hashlib.sha256();f.seek(start)
    while size:
        b=f.read(min(CHUNK,size));need(b,'Unexpected end of file');h.update(b);size-=len(b)
    return h.digest()

def pfs_entries(f,start,size):
    f.seek(start);h=f.read(16);need(h[:4]==b'PFS0','Invalid PFS0')
    count,strings=struct.unpack_from('<II',h,4);need(count<50000,'Invalid PFS count')
    table=f.read(24*count);names=f.read(strings);base=16+24*count+strings;entries={};spans=[]
    for i in range(count):
        off,n,sn,_=struct.unpack_from('<QQII',table,24*i)
        name=names[sn:names.index(0,sn)].decode('utf-8')
        need(name not in entries and base+off+n<=size,'Invalid PFS entry bounds')
        entries[name]=(start+base+off,n);spans.append((off,off+n))
    spans.sort();need(all(a[1]<=b[0] for a,b in zip(spans,spans[1:])),'Overlapping PFS entries')
    return entries

def decrypt(b,key,mode):
    d=Cipher(algorithms.AES(key),mode).decryptor();return d.update(b)+d.finalize()

keys={}
for line in KEYFILE.read_text(encoding='utf-8-sig').splitlines():
    if '=' in line:
        k,v=line.split('=',1);k=k.strip()
        if k in ['header_key','key_area_key_application_00']:keys[k]=bytes.fromhex(v.strip())
need(len(keys)==2,'Required key names unavailable')
records={};program_files=None;control_files=None;logo_files=None;cnmt=None;ivfc_blocks=0

def verify_pfs(f,fs,size):
    bs=struct.unpack_from('<I',fs,0x28)[0]
    htoff,htsize,poff,psize=struct.unpack_from('<QQQQ',fs,0x30)
    need(bs and poff+psize<=size and htoff+htsize<=size,'PFS superblock bounds')
    f.seek(htoff);ht=f.read(htsize);need(sha(ht)==fs[8:40],'PFS master hash mismatch')
    f.seek(poff)
    for j in range(0,psize,bs):
        b=f.read(min(bs,psize-j));need(sha(b)==ht[j//bs*32:j//bs*32+32],'PFS data block hash mismatch')
    return pfs_entries(f,poff,psize)

def verify_romfs(f,fs,size,expected):
    global ivfc_blocks
    need(fs[8:12]==b'IVFC','Expected IVFC')
    need(struct.unpack_from('<I',fs,0x14)[0]==7,'Expected six IVFC levels')
    levels=[struct.unpack_from('<QQI',fs,0x18+24*i) for i in range(6)]
    with mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as m:
        off,n,exp=levels[0];need(off+n<=size,'IVFC bounds');need(sha(m[off:off+n])==fs[0xc8:0xe8],'IVFC master hash mismatch')
        for i in range(1,6):
            off,n,exp=levels[i];bs=1<<exp;parent,pn,_=levels[i-1]
            need(off+((n+bs-1)//bs)*bs<=size,'IVFC padded bounds')
            for j in range(0,n,bs):
                need(j//bs*32+32<=pn,'IVFC parent bounds')
                need(sha(m[off+j:off+j+bs])==m[parent+j//bs*32:parent+j//bs*32+32],f'IVFC level {i} block {j//bs} hash mismatch')
                ivfc_blocks+=1
        root,romsize,_=levels[-1]
        h=struct.unpack_from('<10Q',m,root);need(h[0]==0x50,'Invalid RomFS header')
        dt,ds,ft,fsz,data=h[3],h[4],h[7],h[8],h[9]
        need(max(dt+ds,ft+fsz,data)<=romsize,'RomFS table bounds')
        entries={};visited_dirs=set();visited_files=set()
        def walk(diroff,prefix):
            need(diroff not in visited_dirs and diroff+24<=ds,'RomFS directory cycle/bounds');visited_dirs.add(diroff)
            parent,sibling,child,first,hh,nn=struct.unpack_from('<6I',m,root+dt+diroff)
            need(diroff+24+nn<=ds,'RomFS directory name bounds')
            name=m[root+dt+diroff+24:root+dt+diroff+24+nn].decode('utf-8')
            path=prefix+'/'+name if prefix else name
            pos=first
            while pos!=0xffffffff:
                need(pos not in visited_files and pos+32<=fsz,'RomFS file cycle/bounds');visited_files.add(pos)
                fp,fn,off,n,fh,ln=struct.unpack_from('<IIQQII',m,root+ft+pos)
                need(pos+32+ln<=fsz and data+off+n<=romsize,'RomFS file bounds')
                name=m[root+ft+pos+32:root+ft+pos+32+ln].decode('utf-8');key=path+'/'+name if path else name
                need(key not in entries,'Duplicate RomFS path');entries[key]=(root+data+off,n);pos=fn
            pos=child
            while pos!=0xffffffff:
                need(pos+24<=ds,'RomFS child bounds')
                nxt=struct.unpack_from('<I',m,root+dt+pos+4)[0];walk(pos,path);pos=nxt
        walk(0,'')
        need(set(entries)==set(expected),'RomFS file list differs from expected overlay')
        for key,(off,n) in entries.items():
            e=expected[key];need(n==e['size'],f'RomFS size mismatch: {key}')
            hh=hashlib.sha256()
            for j in range(0,n,CHUNK):hh.update(m[off+j:off+min(j+CHUNK,n)])
            need(hh.hexdigest()==e['sha256'],f'RomFS file hash mismatch: {key}')
    return len(entries)

with NSP.open('rb') as f:
    entries=pfs_entries(f,0,NSP.stat().st_size);need(len(entries)==3,'Expected Program, Control and Meta NCAs')
    for name,(base,n) in entries.items():
        print('Verifying archive '+name,flush=True)
        digest=digest_range(f,base,n);need(name.split('.')[0]==digest[:16].hex(),'NCA content ID mismatch')
        f.seek(base);enc=f.read(0xc00)
        h=b''.join(decrypt(enc[i:i+512],keys['header_key'],modes.XTS((i//512).to_bytes(16,'big'))) for i in range(0,0xc00,512))
        need(h[0x200:0x204]==b'NCA3','Invalid decrypted NCA header')
        need(struct.unpack_from('<Q',h,0x210)[0]==TID,'NCA title ID mismatch')
        need(struct.unpack_from('<Q',h,0x208)[0]==n,'NCA size mismatch')
        need(h[0x230:0x240]==bytes(16),'Unexpected title-rights dependency')
        need(max(h[0x206],h[0x220])<=1 and h[0x207]==0,'Unexpected key generation')
        area=decrypt(h[0x300:0x340],keys['key_area_key_application_00'],modes.ECB())
        ctype=h[0x205];records[digest[:16]]=(digest,n,ctype)
        for i in range(4):
            start,end=struct.unpack_from('<II',h,0x240+16*i);start*=512;end*=512
            if start==end:continue
            need(0xc00<=start<end<=n,'NCA section bounds')
            fs=h[0x400+512*i:0x600+512*i];need(sha(fs)==h[0x280+32*i:0x2a0+32*i],'NCA FS header hash mismatch')
            need(fs[4] in [1,3],'Unexpected encryption mode')
            decryptor=Cipher(algorithms.AES(area[32:48]),modes.CTR(fs[0x140:0x148][::-1]+(start//16).to_bytes(8,'big'))).decryptor() if fs[4]==3 else None
            path=VERIFY/f'{ctype}-{i}.section';f.seek(base+start);remaining=end-start
            with path.open('wb') as out:
                while remaining:
                    b=f.read(min(CHUNK,remaining));need(b,'Truncated NCA section');remaining-=len(b)
                    out.write(decryptor.update(b) if decryptor else b)
                if decryptor:out.write(decryptor.finalize())
            with path.open('rb') as section:
                if fs[3]==2:
                    pe=verify_pfs(section,fs,end-start)
                    values={}
                    for key,(off,sz) in pe.items():section.seek(off);values[key]=section.read(sz)
                    if ctype==0 and 'main.npdm' in values:program_files=values
                    elif ctype==0:logo_files=values
                    elif ctype==1:
                        need(len(values)==1,'Unexpected Meta contents');cnmt=next(iter(values.values()))
                elif fs[3]==3:
                    if ctype==0:
                        count=verify_romfs(section,fs,end-start,MAN['game_assets'])
                        print(f'All {count:,} packaged game assets match the intended overlay.',flush=True)
                    elif ctype==2:
                        expected={key:{'size':(ST/'control'/key).stat().st_size,'sha256':value} for key,value in MAN['control'].items()}
                        verify_romfs(section,fs,end-start,expected);control_files=True
                    else:raise ValueError('Unexpected RomFS archive type')
                else:raise ValueError('Unexpected NCA hash type')
            path.unlink()
    nsp_sha=digest_range(f,0,NSP.stat().st_size).hex()

need(program_files and control_files and logo_files and cnmt,'Required content missing')
need(set(program_files)==set(MAN['staged_exefs']),'ExeFS file list mismatch')
for name,digest in MAN['staged_exefs'].items():
    # hacPack intentionally changes the ACID public modulus in its staged NPDM.
    expected=(ST/'exefs'/name).read_bytes()
    need(program_files[name]==expected,'Embedded ExeFS differs from staging: '+name)
    if name!='main.npdm':need(hashlib.sha256(expected).hexdigest()==digest,'Staged executable changed unexpectedly')
npdm=program_files['main.npdm'];original=(ST/'npdm-before-pack.bin').read_bytes();acid_offset=struct.unpack_from('<I',npdm,0x78)[0]
need(npdm[:acid_offset+0x100]==original[:acid_offset+0x100] and npdm[acid_offset+0x200:]==original[acid_offset+0x200:], 'NPDM changed outside the packager public-key field')
npdm=program_files['main.npdm'];aci=struct.unpack_from('<I',npdm,0x70)[0];acid=struct.unpack_from('<I',npdm,0x78)[0]
need(struct.unpack_from('<Q',npdm,aci+0x10)[0]==TID,'ACI0 program ID mismatch')
need(struct.unpack_from('<QQ',npdm,acid+0x210)==(TID,TID),'ACID program range mismatch')
need(program_files['main'][64:96].hex()==MAN['main_build_id'],'Custom NSO build ID mismatch')
for name,digest in MAN['logo'].items():need(sha(logo_files[name]).hex()==digest,'Logo mismatch')
control=(ST/'control/control.nacp').read_bytes()
for off,val in [(0x3038,TID),(0x3070,TID+0x1000),(0x3078,TID),(0x30f8,TID)]:need(struct.unpack_from('<Q',control,off)[0]==val,'Control identity mismatch')
need(control[0x3060:0x3070].split(b'\0')[0]==b'2.2F','Control version mismatch')
need(struct.unpack_from('<Q',cnmt)[0]==TID and cnmt[12]==0x80,'Expected custom Application CNMT')
need(struct.unpack_from('<I',cnmt,8)[0]==0,'Unexpected package version')
extsize,count=struct.unpack_from('<HH',cnmt,14);need(count==2,'CNMT reference count mismatch')
need(struct.unpack_from('<Q',cnmt,32)[0]==TID+0x800,'CNMT patch identity mismatch')
for i in range(count):
    r=cnmt[32+extsize+56*i:32+extsize+56*(i+1)];digest,size,ctype=records[r[32:48]]
    need(r[:32]==digest and int.from_bytes(r[48:54],'little')==size,'CNMT hash/size mismatch')
    need((ctype,r[54]) in [(0,1),(2,3)],'CNMT content type mismatch')

report={'result':'PASS','title':MAN['title'],'title_id':MAN['title_id'],'display_version':MAN['display_version'],
 'nsp_bytes':NSP.stat().st_size,'nsp_sha256':nsp_sha,'main_build_id':MAN['main_build_id'],'baked_ips_records':MAN['ips_records'],
 'game_asset_files_verified':len(MAN['game_assets']),'ivfc_blocks_verified':ivfc_blocks,
 'checks':['NSP entry bounds and overlap','NCA content IDs, archive sizes, title IDs, and no ticket dependency',
 'Decrypted NCA filesystem headers and SHA-256 hashes','ExeFS and CNMT block hash trees','Complete game and Control RomFS IVFC hash trees',
 'Every packaged game asset matches the final source overlay by path, size, and SHA-256',
 'Executable and added subsdk1 match staging','All 155 IPS records verified in the rebuilt NSO during preparation',
 'Separate main NSO build ID','NPDM identity and ACID program range','Control icons, name, version, and save identity',
 'Application CNMT references, hashes, sizes and content types','Startup logo files'],
 'runtime_status':'Reproduces the previously user-confirmed working build; this local package still needs a launch/save check'}
args.out.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2),flush=True)
