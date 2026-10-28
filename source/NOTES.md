# Implementation and credits

Builder version: **1.0.0**. Supported source: **Brilliant Diamond 1.3.0 + Luminescent Platinum 2.2F BD**.

## Input contract

`builder/supported-inputs.json` contains relative filenames, sizes, and SHA-256 fingerprints for the supported original game/mod assets and small inputs. It contains no executable bytes, patch bytes, keys, game assets, or absolute personal paths. Full asset hashes are checked while copying files into a private staging directory. Unsupported versions are deliberately rejected.

Required console key names are `header_key` and `key_area_key_application_00`. Key values are consumed locally and never intentionally printed, recorded in build metadata, copied into staging, or included in output reports.

## Executable preparation

The source main NSO build ID is `94CEAE325C205C4B9D6F7235552F28FD`. LZ4 segments are decompressed and their original SHA-256 values verified. The user-supplied IPS32 file has 155 records and SHA-256 `f4fe05e206348f8e13c80f0d23539dd1d6952da8036d32a0fcabf4daa78f4f50`.

Patch offsets include the 0x100-byte NSO header. Writes target the corresponding mapped segment bytes. Every write is bounded to a segment; the patched code is recompressed and round-trip checked with fresh segment hashes. The build ID is SHA-256 of the domain tag `Luminescent Platinum 2.2F standalone\0` followed by the patched mapped image. The supported inputs yield `0f5bc99cb90c2a8fb7bb30ecec93bbdae5c4d15a3c96e34c2ea87d23f7f6a4c6`.

`subsdk1` is supplied by the user and included unchanged. The original `rtld`, `sdk`, and `subsdk0` are retained. No additional runtime IPS installation is needed.

The NSO uncompressed layout follows [hactool's NSO implementation](https://github.com/SciresM/hactool/blob/master/nso.c). Runtime IPS selection and header-offset handling are documented in [Atmosphère's loader](https://github.com/Atmosphere-NX/Atmosphere/blob/master/docs/components/modules/loader.md).

## Application identity

Custom title ID: `0100E04C554D0000`. Original BD: `0100000011D90000`. NPDM ACI0 and ACID range are set to the custom identity; the process name is `LuminescentPlt`. The original filesystem permissions for reading other Pokémon saves are retained. This supported descriptor has no explicit old-BD save-owner grant to replace.

The 1.3.0 Control metadata is retained except for application titles/publisher, display version, presence identity, add-on base ID, save owner, and pseudo-device seed. The display name is `Pokémon Luminescent Platinum`, publisher `Team Luminescent`, and version `2.2F`. LocalCommunicationId grants are preserved: they authorize networking and do not select save ownership. Control resource limits and save sizes remain those of the supplied game.

The custom ID was checked against the owner's Ruby, Sapphire, and Emerald W5 package IDs during the initial build. It is not a globally reserved ID or a check of every user's installed library. Reusing the ID intentionally updates the same application/save namespace.

## Packaging and verification

hacPack creates Program, Control, and Application Meta NCAs with content version 0, then an NSP. Its default NPDM self-signing step changes the ACID public modulus in staging; verification allows only that expected NPDM change. The source metadata stays untouched.

The independent verifier decrypts archives in bounded chunks and verifies NCA header/section identities, content IDs, sizes, ExeFS/CNMT hashes, full RomFS IVFC trees, and every final game file against the staged overlay manifest. It checks embedded executable/control/logo contents and save identity. No Nintendo fixed-key signature authenticity is claimed: this is a custom rebuilt package.

Builds use unique `.build/run-...` directories. The new NSP is moved to `Release` only after successful verification. Files in `.build` are private; they are not part of the distributable archive. Runtime installation, launch, save/reload, and gameplay checks remain separate from package verification.

## Credits and licenses

- **Team Luminescent**: the mod, its assets, injected module, and IPS patch. Users supply these separately; retain the original notices. [Team Luminescent](https://luminescent.team/), [ExeFS project](https://github.com/TeamLumi/Luminescent_ExLaunch).
- **Nintendo / ILCA / The Pokémon Company and relevant rights holders**: original game content, supplied separately by the user.
- **The-4n and hacPack contributors**: open-source packaging tool. `tools/hacPack-LICENSE.txt`, `tools/hacPack-README.md`, and `tools/hacPack-source.zip` accompany the supplied binary.
- **SciresM / hactool and Atmosphère contributors**: public format and loader implementation references.
- [Gamingwithgoose/Pokemon-Emerald-Switch-Edition](https://github.com/Gamingwithgoose/Pokemon-Emerald-Switch-Edition): requested walkthrough/launcher organization.

The MIT license in the pack covers its original builder scripts and documentation. It does not grant rights to Nintendo content, user-supplied mod/artwork, or third-party tools. Third-party licenses remain separate.
