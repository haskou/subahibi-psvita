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

Keep at least 2.3 GB free on `ux0:`.

1. Create `ux0:data/Subahibi/` in VitaShell.
2. Copy all three RPA files into `ux0:data/Subahibi/` by USB or FTP.
3. Copy `Subahibi.vpk` to `ux0:data/`. Do not install it directly from
   `uma0:`; first copy it onto `ux0:` so VitaShell reads and extracts it from
   the destination filesystem.
4. In VitaShell, select `Subahibi.vpk`, press Cross and confirm installation.
5. Confirm that all three RPA files remain in `ux0:data/Subahibi/`, then launch
   **Subahibi**.

Do not copy the RPA files into `ux0:app/SHBI00001/game/`. That application
directory is replaced when a VPK is reinstalled. The port reads media directly
from `ux0:data/Subahibi/`, so an update requires installing only the new VPK
plus any RPA file whose hash in `SHA256SUMS` differs from the copy on `ux0:`.

If an earlier build already has the archives under
`ux0:app/SHBI00001/game/`, use VitaShell to **move** all three files to
`ux0:data/Subahibi/` before installing this VPK. A move on the same `ux0:`
filesystem should not retransmit their contents.

## Diagnostics

If startup fails, copy the files that exist before launching the game again:

```text
ux0:app/SHBI00001/log.txt
ux0:app/SHBI00001/traceback.txt
ux0:app/SHBI00001/errors.txt
ux0:data/*.psp2dmp
ux0:data/psp2core*
```
