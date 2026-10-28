"""Synthetic fixtures only: no games, mod bytes, console keys, or NSPs required."""
from pathlib import Path
import hashlib,importlib.util,json,shutil,struct,subprocess,sys,tempfile,unittest
import lz4.block
from unittest import mock

PACK=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PACK/'builder'))
import inputs
spec=importlib.util.spec_from_file_location('lumi_builder',PACK/'builder/build.py')
build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
digest=lambda b:hashlib.sha256(b).hexdigest()

class InputChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        for folder in inputs.FOLDERS:(self.root/folder).mkdir(parents=True,exist_ok=True)
        (self.root/'tools').mkdir()
        small={'switch files/exefs/main':b'synthetic game executable','Luminescent mod/exefs/subsdk1':b'synthetic mod module'}
        for name,data in small.items():(self.root/name).write_bytes(data)
        (self.root/'tools/hacpack.exe').write_bytes(b'synthetic tool')
        (self.root/'switch files/romfs/Data').mkdir();(self.root/'Luminescent mod/romfs/Data').mkdir()
        (self.root/'switch files/romfs/Data/base').write_bytes(b'base asset')
        (self.root/'Luminescent mod/romfs/Data/mod').write_bytes(b'mod asset')
        (self.root/'switch files/prod.keys').write_text('header_key = '+'12'*32+'\nkey_area_key_application_00 = '+'34'*16+'\n')
        self.support={'small_files':{p:digest(b) for p,b in small.items()},'tool_sha256':digest(b'synthetic tool'),
          'layers':{'game':{'Data/base':{}},'luminescent':{'Data/mod':{}}}}
    def check(self):inputs.check_inputs(self.root,self.support)
    def test_valid_inputs_are_unchanged(self):
        before={p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.check()
        after={p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before,after)
    def test_missing_required_file_names_the_path(self):
        (self.root/'switch files/exefs/main').unlink()
        with self.assertRaisesRegex(ValueError,'switch files/exefs/main'):self.check()
    def test_wrong_game_version_is_rejected(self):
        (self.root/'switch files/exefs/main').write_bytes(b'other version')
        with self.assertRaisesRegex(ValueError,'Unsupported or modified input'):self.check()
    def test_changed_packager_is_rejected(self):
        (self.root/'tools/hacpack.exe').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'packager'):self.check()
    def test_invalid_key_value_is_not_echoed(self):
        secret='DO_NOT_DISPLAY_THIS_VALUE'
        (self.root/'switch files/prod.keys').write_text('header_key = '+secret)
        with self.assertRaises(ValueError) as result:self.check()
        self.assertNotIn(secret,str(result.exception));self.assertIn('header_key',str(result.exception))
    def test_missing_base_asset_is_rejected(self):
        (self.root/'switch files/romfs/Data/base').unlink()
        with self.assertRaisesRegex(ValueError,'missing files'):self.check()
    def test_unrelated_asset_is_rejected(self):
        (self.root/'Luminescent mod/romfs/extra').write_bytes(b'extra')
        with self.assertRaisesRegex(ValueError,'unexpected files'):self.check()
    def test_extra_nested_romfs_is_rejected(self):
        (self.root/'switch files/romfs/Data').rename(self.root/'switch files/romfs/romfs')
        with self.assertRaisesRegex(ValueError,'RomFS layout'):self.check()
    def test_mod_notices_and_gitkeep_are_allowed(self):
        (self.root/'Luminescent mod/romfs/README.md').write_text('Synthetic notice')
        (self.root/'Luminescent mod/romfs/LICENSE.txt').write_text('Synthetic license')
        (self.root/'switch files/romfs/.gitkeep').touch();self.check()
    def test_multiple_icons_are_rejected(self):
        for name in ['a.png','b.jpg']:(self.root/'Homescreen Icon'/name).touch()
        with self.assertRaisesRegex(ValueError,'only one image'):self.check()

class ExecutableChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'fixture'
    def test_ips32_raw_and_run_records(self):
        self.path.write_bytes(b'IPS32'+struct.pack('>IH',0x104,2)+b'AB'+struct.pack('>IHHB',0x108,0,3,0x7f)+b'EEOF')
        self.assertEqual(build.read_ips(self.path),[(0x104,b'AB'),(0x108,b'\x7f'*3)])
    def test_truncated_patch_is_rejected(self):
        self.path.write_bytes(b'IPS32'+struct.pack('>IH',0x104,4)+b'AB')
        with self.assertRaisesRegex(ValueError,'Truncated'):build.read_ips(self.path)
    def test_wrong_patch_format_is_rejected(self):
        self.path.write_bytes(b'PATCH123')
        with self.assertRaisesRegex(ValueError,'IPS32'):build.read_ips(self.path)
    def make_nso(self):
        h=bytearray(256);h[:4]=b'NSO0';struct.pack_into('<I',h,12,0x3f);out=bytearray(h)
        for i in range(3):
            data=bytes([i+1])*64;compressed=lz4.block.compress(data,store_size=False)
            struct.pack_into('<III',out,16+i*16,len(out),i*0x1000,len(data))
            struct.pack_into('<I',out,96+i*4,len(compressed));out[160+i*32:192+i*32]=hashlib.sha256(data).digest();out.extend(compressed)
        self.path.write_bytes(out)
    def test_valid_nso_decompression_and_hashes(self):
        self.make_nso();h,data,segments=build.unpack_nso(self.path)
        self.assertEqual(segments,[(0,64),(0x1000,64),(0x2000,64)])
        self.assertEqual(data[0x2000:0x2040],b'\x03'*64)
    def test_corrupted_nso_hash_is_rejected(self):
        self.make_nso();data=bytearray(self.path.read_bytes());data[160]^=1;self.path.write_bytes(data)
        with self.assertRaisesRegex(ValueError,'Invalid NSO segment'):build.unpack_nso(self.path)

class FailedBuildChecks(unittest.TestCase):
    def test_publish_failure_restores_previous_nsp_and_reports(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);stage=root/'stage';dest=root/'Release';stage.mkdir();dest.mkdir()
            names=['verification.json','build-record.json','Pokemon_Luminescent_Platinum.nsp']
            for name in names:
                (dest/name).write_bytes(('old '+name).encode());(stage/name).write_bytes(('new '+name).encode())
            real_replace=build.os.replace
            def fail_nsp(source,target):
                if Path(source)==stage/names[-1] and Path(target)==dest/names[-1]:raise OSError('synthetic locked output')
                return real_replace(source,target)
            with mock.patch.object(build.os,'replace',side_effect=fail_nsp):
                with self.assertRaisesRegex(OSError,'synthetic locked'):build.publish_release(stage,dest,stage/names[-1])
            for name in names:self.assertEqual((dest/name).read_bytes(),('old '+name).encode())
    def test_publish_commits_verified_outputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);stage=root/'stage';dest=root/'Release';stage.mkdir();dest.mkdir()
            names=['verification.json','build-record.json','Pokemon_Luminescent_Platinum.nsp']
            for name in names:(stage/name).write_bytes(('new '+name).encode())
            build.publish_release(stage,dest,stage/names[-1])
            for name in names:self.assertEqual((dest/name).read_bytes(),('new '+name).encode())
    def test_missing_inputs_preserve_the_previous_nsp_and_release_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            shutil.copytree(PACK/'builder',root/'builder',ignore=shutil.ignore_patterns('__pycache__'))
            (root/'Release').mkdir();previous=root/'Release/Pokemon_Luminescent_Platinum.nsp';previous.write_bytes(b'synthetic previous release')
            result=subprocess.run([sys.executable,str(root/'builder/build.py')],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertIn('Missing files',result.stderr)
            self.assertEqual(previous.read_bytes(),b'synthetic previous release')
            self.assertFalse((root/'.build/build.lock').exists())

if __name__=='__main__':unittest.main(verbosity=2)
