# Desktop Bridge — this Mac → Windows desktop

How to reach the Windows desktop (`DESKTOP-HMGN413`) from this Mac. Used by
deepclaw / Nova and any other agent or tool running here.

## Target
- **Host:** `DESKTOP-HMGN413` (resolves via `/etc/hosts` → `192.168.12.244`)
- **User:** `load` (a *local Administrator* account)
- **Auth:** passwordless SSH (ed25519 key). No password prompt.
- The desktop's OpenSSH server is enabled (port 22 open on the LAN).

## How to connect

### Option A — direct SSH (terminal / any agent / OpenCode / pi)
```sh
ssh load@DESKTOP-HMGN413 "<command>"          # interactive-free when no TTY needed
ssh -o BatchMode=yes load@DESKTOP-HMGN413 whoami   # prove key auth, no prompt
```

### Option B — deepclaw / Nova skills (any agent driving Nova)
Both skills are auto-loaded by Nova's `SkillRegistry` from `~/.deepclaw/skills/`.

**`run_on_desktop`** — run a shell command on the desktop (cmd.exe):
```
run_on_desktop(command="<shell command>")
run_on_desktop(command="hostname")   # -> DESKTOP-HMGN413
```

**`desktop_file`** — read / copy files to and from the desktop over SSH:
```
desktop_file(action="read",      remote_path="C:\\Users\\load\\Desktop\\note.txt")
desktop_file(action="copy_to",   remote_path="C:\\Users\\load\\note.txt", local_path="/tmp/note.txt")  # Mac -> desktop
desktop_file(action="copy_from", remote_path="C:\\Users\\load\\note.txt", local_path="/tmp/note.txt")  # desktop -> Mac
```
For `scp` the path is normalized to forward slashes automatically; for `read`
(cmd `type`) backslashes are fine.

## Why the key lives in ProgramData (not `.ssh`)
`load` is a member of the **Administrators** group, so Windows OpenSSH sshd
ignores `C:\Users\load\.ssh\authorized_keys` and instead requires
`C:\ProgramData\ssh\administrators_authorized_keys`. Our public key
(`~/.ssh/id_ed25519.pub`) is appended there, with permissions:
`SYSTEM:(R)` + `BUILTIN\Administrators:(R)`, inheritance removed.
This is the reason a plain `~/.ssh/authorized_keys` on the desktop did not work.

## This-Mac side setup
- `/etc/hosts` contains: `192.168.12.244 DESKTOP-HMGN413` (added by tk) so the
  name resolves locally.
- Private key: `~/.ssh/id_ed25519` (no passphrase). Public key:
  `~/.ssh/id_ed25519.pub`.

## Gotchas
- The remote default shell is **cmd.exe**. Use Windows paths (backslashes) and
  cmd syntax for remote commands. For PowerShell, prefix:
  `powershell -NoProfile -Command "..."`.
- The desktop must be on the same LAN (`192.168.12.x`) for `192.168.12.244` to
  route. Over a different network, use the router's public IP + port forward
  (or a tunnel) instead of the bare LAN IP.

## Security notes
- This Mac's `tk` account holds the private key, granting **passwordless admin
  SSH** to the desktop. LAN-scoped. Anyone with this account (or the key file)
  can act as `load` on the desktop.
- The key has no passphrase. Add one (`ssh-keygen -p`) if you want a second
  factor — note that then non-interactive/agent use would need an ssh-agent.
