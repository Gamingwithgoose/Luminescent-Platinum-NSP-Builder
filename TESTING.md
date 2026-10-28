# Validation — builder 1.0.0

Validated October 28, 2026, on Windows with Python **3.14.6 x64** and the exact package versions in `builder/requirements.txt`.

## Completed checks

- Fresh Python dependency installation into an isolated environment.
- Windows PowerShell launcher first-run setup, dependency imports, correct working directory, and build-script invocation, using a synthetic launcher fixture in a path containing spaces.
- Second launcher run reusing the environment without reinstalling packages.
- `-PrepareFolders` and missing-input reporting from another working directory.
- **18 automated tests** covering supported-input checks, key-value redaction in errors, missing/extra/nested asset trees, changed packager/game files, multiple icons, IPS32 parsing, NSO hashes, preservation of the previous NSP on failure, successful release publication, and restoration of previous files after a simulated publication error.
- A full private build using the owner's supplied BD 1.3.0 extraction, Luminescent 2.2F BD, keys, and icon.
- Finished-package verification: **19,282** merged game files and **325,158** IVFC blocks, plus Program/Control/Meta identities, content references, executable contents, icon/control data, logo contents, and save ownership.
- Comparison with the earlier user-confirmed working package: identical staged executable modules, NPDM, Control metadata/icons, logo files, and the full merged asset manifest. Archive layout and therefore the NSP's overall hash can differ.
- Final release-publication routine exercised with the real verified NSP.
- Distribution allowlist and private-content audit before creating the public build-pack ZIP. The distributable has empty input/Release folders and contains no games, mod assets, keys, saves, artwork, or finished NSPs.

## Runtime scope

The owner reported that the initial standalone NSP worked. The target and extent of that test were not specified. A new package has not been claimed as independently tested on every Switch/emulator version. Each user should perform the launch, early-game installation check, save, close, and reload steps in the README.

The builder is scoped to **Brilliant Diamond 1.3.0 + Luminescent Platinum 2.2F BD**. Other game versions, Pearl inputs, pre-merged dumps, other mod versions, networking changes, and existing-save migrations are outside this release's support.

## Run the automated checks

After the builder has installed its Python dependencies, open PowerShell in the pack folder and run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

These tests use synthetic fixtures. They do not require game/mod inputs, real console keys, a Switch, or an emulator. The separate private full-build test used personal inputs outside the distributable and is not shipped.
