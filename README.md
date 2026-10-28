# Pokémon Luminescent Platinum — standalone NSP builder

Build **Luminescent Platinum 2.2F BD** as its own complete Switch application, alongside Brilliant Diamond and Shining Pearl. It uses title ID **`0100E04C554D0000`**, a separate save owner, and your selected HOME menu icon.

**The builder runs on your Windows PC only while creating and verifying the NSP. Once it finishes, close it. Nothing needs to stay running while you play.** It does not install the package, connect to a console, or run an emulator.

The pack contains scripts, input fingerprints, and the open-source packager. Game files, mod files, keys, saves, artwork, and finished NSPs are **not included**. Supply your own files.

## What you need to supply

| Your file or folder | Put it here |
| --- | --- |
| Your console keyset, named `prod.keys` | `switch files/prod.keys` |
| Brilliant Diamond **1.3.0** ExeFS: `main`, `main.npdm`, `rtld`, `sdk`, `subsdk0` | `switch files/exefs/` |
| Complete Brilliant Diamond **1.3.0** RomFS, with the base game and update already resolved together | `switch files/romfs/` |
| **1.3.0 update's** `control.nacp`, from Control #0 | `switch files/control 0/control.nacp` |
| Base game's `NintendoLogo.png` and `StartupMovie.gif`, from the program's logo section | `switch files/logo/` |
| Extracted **Luminescent Platinum 2.2F BD** mod, containing `exefs` and `romfs` | `Luminescent mod/` |
| Optional PNG, JPG, JPEG, WebP, or BMP HOME menu image | `Homescreen Icon/` |

Use **Brilliant Diamond**, original title ID `0100000011D90000`. Shining Pearl dumps and other mod releases are not supported by this builder. Keep the game dump and mod in their separate input folders; do not merge them yourself.

The supported game executable has build ID `94CEAE325C205C4B9D6F7235552F28FD`. The builder also checks fingerprints of the other required files and the full game/mod asset trees, rather than relying on folder names alone. A partial, modified, or different extraction will stop the build.

This walkthrough starts with your own extracted files. It does not cover acquiring games, keys, or dumps. A base-game extraction alone is insufficient: the supplied game RomFS and ExeFS must already include **1.3.0**.

## 1. Install Python

Use **Python 3.14, 64-bit**, on a Windows 10 or Windows 11 x64 PC. Testing used Python **3.14.6**. See [Required Software.txt](Required%20Software.txt) for the official download link and package versions.

Keep pip and the Python launcher enabled. If the installer offers **Add Python to PATH**, select it. Close and reopen PowerShell after installation.

The first build needs an internet connection to install the pinned Python packages into this pack's `.venv` folder. Later builds reuse that environment. No administrator rights are required.

## 2. Extract the entire pack

Extract the ZIP to a short, writable folder, such as **`C:\LPBuilder`**. Do not run it from inside the ZIP. Keep `builder`, `tools`, and the build launchers together.

Allow **at least 30 GiB of free space after adding your inputs**. Intermediate archives and the verification pass require more space than the final NSP.

The build-pack ZIP includes the empty input folders. If you used GitHub's **Download ZIP** or cloned a repository, create those folders by opening PowerShell in the extracted folder and running:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build.ps1 -PrepareFolders
```

The normal build command also creates missing input folders and then reports the files you need to add.

## 3. Add your files

Arrange the files exactly like this:

```text
LPBuilder/
  build.bat
  build.ps1
  README.md
  switch files/
    prod.keys
    exefs/
      main
      main.npdm
      rtld
      sdk
      subsdk0
    romfs/
      Data/
        ...complete 1.3.0 game assets...
    control 0/
      control.nacp
    logo/
      NintendoLogo.png
      StartupMovie.gif
  Luminescent mod/
    exefs/
      94CEAE325C205C4B9D6F7235552F28FD.ips
      subsdk1
      ...mod notices, if supplied...
    romfs/
      Data/
        ...2.2F BD mod assets...
  Homescreen Icon/
  Release/
  builder/
  tools/
  source/
  tests/
```

Copy the **contents** of each extracted folder into its matching folder. Avoid `romfs/romfs/Data`, `exefs/exefs/main`, or `control 0/0/control.nacp`.

For example, if your mod extraction is named `Luminescent Platinum 2.2F BD`, copy its `exefs` and `romfs` folders directly inside `Luminescent mod`. Keep the original notices with those folders. Extract the mod with 7-Zip, as its included installation notes recommend.

Keep the ExeFS names unchanged: do not add `.bin` or `.nso`. Enable filename extensions in Explorer if necessary; `prod.keys.txt` is a different filename.

For your own icon, place **one image** in `Homescreen Icon`. A square image works best. The builder resizes it to 256 × 256 and converts it to JPEG. Leave the folder empty to use a generated silver **LP** emblem. The Giratina artwork used in the initial personal build is not distributed in this pack.

The original Control icons are not required. Only the update's `control.nacp` is used from that section.

## 4. Build the NSP

Double-click **`build.bat`**. It checks the inputs, prepares its local Python environment, merges the assets, applies the executable patch, packages the game, and verifies the finished NSP. The window stays open so you can read the result.

Or run this in PowerShell from the pack folder:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

The execution-policy setting applies only to that PowerShell process. Both launchers run the same builder.

Wait for **Done** and **Verification: PASS**. Your package will be here:

```text
Release/Pokemon_Luminescent_Platinum.nsp
```

The same folder contains:

- `verification.json`: package integrity results, file count, title ID, and NSP SHA-256.
- `build-record.json`: builder version, selected icon type, source versions, and package details.

Building can take several minutes. Progress messages appear during staging and packaging; the complete packager and verification output is stored in `.build/run-.../build.log`.

Your supplied files stay unchanged. A successful rebuild replaces the existing NSP in `Release`. An unsuccessful build does not publish a new NSP, so a previous file may still be there: check the final message before using it.

**Close the builder after it finishes. The installed game does not depend on the builder, Python, or your PC.**

## 5. Install and test

### Modded Switch

1. Back up any existing Luminescent save using your normal save manager.
2. Install `Release/Pokemon_Luminescent_Platinum.nsp` with the custom-package installer/setup you normally use.
3. Launch **Pokémon Luminescent Platinum** from its own HOME menu icon.
4. Start a new game in English. Check the modified language-selection screen and expected mod features.
5. Visit the first Pokémon Center and check for an installation-error message or unexpected teleport.
6. Save, close the game completely, reopen it, and load the save.

The NSP contains the full resolved game and mod. Brilliant Diamond does not need to remain installed for this separate entry to run. The package is a community modification and requires an environment that supports custom packages.

The package is about **5.37 GB**, larger than FAT32's single-file limit. Use your usual USB/network installation method or an installer-supported split-file method if the SD card is FAT32.

### Emulator

1. Add or install the NSP using your emulator's normal game-library flow.
2. Confirm that its title ID is `0100E04C554D0000` and its display version is `2.2F`.
3. Do not apply the ordinary Brilliant Diamond update or another copy of the Luminescent mod to this custom entry: both are already incorporated.
4. Test launch, early gameplay, saving, and loading after restarting the game.

### Keeping ordinary Brilliant Diamond vanilla

The custom title ID separates this application from BD/SP, but an old mod installation can still affect the original BD entry.

- Disable its former Luminescent RomFS/ExeFS override under `atmosphere/contents/0100000011D90000/`, or disable the mod on the normal BD entry in your emulator.
- On Switch, also disable the old Luminescent file named `94CEAE325C205C4B9D6F7235552F28FD.ips` under `atmosphere/exefs_patches/`. Those patches select the executable by build ID. The custom NSP has its own main build ID.
- Confirm that LP and the original games each save and reload their own progress.

An existing LP installation using **this same custom title ID** is the same application. Rebuilding with another icon does not create another title or save. Official BD updates do not update this custom application; a future LP version needs a supported builder revision or a compatible custom update.

## If the build stops

| Message or symptom | What to check |
| --- | --- |
| Python missing or wrong version | Install Python 3.14 x64, reopen the terminal, and try again. |
| Package installation failed | Check the internet connection or proxy settings. Use the pinned versions in `Required Software.txt`. |
| Missing files | Use the exact paths listed in the message. Check for extra nested folders and hidden filename extensions. |
| Unsupported or modified input | Use the original BD 1.3.0 extraction and 2.2F **BD** mod. Base 1.0.0, Pearl, pre-merged assets, and other mod versions are rejected. |
| Missing/unexpected RomFS paths | Copy the complete extracted folders. Remove unrelated files from the input trees. |
| Unsupported or changed asset | Recheck the indicated file against your original extraction. Partial or mixed-version assets will not build. |
| More than one icon | Keep one supported image or leave the folder empty. |
| Path too long | Extract to a shorter location such as `C:\LPBuilder`. |
| Not enough space | Free at least 30 GiB beyond the supplied inputs. Previous `.build` runs can use substantial space. |
| Another build may be running | Close the other build. If no builder is running after a crash, remove `.build/build.lock` and retry. |
| Packaging or verification failed | Keep that run's `.build/run-.../build.log` for troubleshooting. The new NSP is not published to `Release`. |
| Damaged Python environment | Remove `.venv`, then run again to recreate it. |

The `.build` folder contains private game files and can be removed after a successful build, with the builder closed. Deleting `.venv` makes the next build reinstall its Python packages. Keep keys, game/mod inputs, saves, `.build`, and finished NSPs out of public repository uploads; `.gitignore` excludes them.

If an installed game fails, record the target, emulator/firmware version, error code, and whether it happened at launch, the Pokémon Center, saving, or loading. A successful package check verifies its contents, not every runtime behavior.

## What the builder changes

The builder overlays the mod onto the resolved 1.3.0 game assets, applies the supplied IPS32 records to decompressed NSO code, regenerates segment hashes, and includes the mod's `subsdk1`. It assigns a distinct main build ID and consistent application/save metadata while retaining the original communication permissions. It creates new Program, Control, and Application Meta archives and packages them into an NSP.

Every build verifies archive hashes, metadata references, executable contents, icon/control metadata, and all **19,282** merged asset files before publishing the result. See [TESTING.md](TESTING.md) for validation scope and [source/NOTES.md](source/NOTES.md) for implementation details and credits.

This walkthrough follows the organization of the [Pokémon Emerald Switch Edition build pack](https://github.com/Gamingwithgoose/Pokemon-Emerald-Switch-Edition). The projects require different source files and are not interchangeable.
