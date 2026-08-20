# Installing

## Verify the release

Download all four payload files and `SHA256SUMS` into one directory:

```text
Subahibi.vpk
Subahibi-images.rpa
Subahibi-audio-01.rpa
Subahibi-audio-02.rpa
SHA256SUMS
```

On Linux or macOS:

```sh
shasum -a 256 -c SHA256SUMS
```

On Windows, run `certutil -hashfile FILE SHA256` for each payload and compare
the values with `SHA256SUMS`.

## Install with VitaShell

Keep at least 2.6 GB free on `ux0:`.

1. Delete an older `SHBI00001` bubble if one is installed.
2. Copy the VPK and all three RPA files to `ux0:data/Subahibi/` by USB or FTP.
3. In VitaShell, select `Subahibi.vpk`, press Cross and confirm installation.
4. Open `ux0:data/Subahibi/` in VitaShell and copy the three `.rpa` files.
5. Open `ux0:app/SHBI00001/game/` and paste them there.
6. Confirm that all three RPA files are present, then launch **Subahibi**.
7. Delete `ux0:data/Subahibi/` after the game has been tested successfully.

The media files are copied directly rather than installed inside the VPK to
avoid VitaShell's failure on the previous VPK larger than 2 GiB.

## Diagnostics

If startup fails, copy the files that exist before launching the game again:

```text
ux0:app/SHBI00001/log.txt
ux0:app/SHBI00001/traceback.txt
ux0:app/SHBI00001/errors.txt
ux0:data/*.psp2dmp
ux0:data/psp2core*
```
