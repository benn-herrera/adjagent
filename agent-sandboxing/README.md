# Sandboxing Your Coding Agent

Running a coding agent under your own account, with your privileges, keys and logins, is Russian
roulette. This setup runs it as a second, unprivileged local user instead: `agent-user`, primary
group `agent-group`. You are a member of that group, so everything the agent writes is yours to read
and edit; the agent can write only its own home, the system temp directories, and your projects
tree, and holds no credential for anything outside the machine. The agent commits. You clone, fetch,
pull and push from your own shell, where a small `git` function refuses everything else and points
you to the agent shell.

It is built against accidents, not malice. Most agent mishaps come from underspecified tasking
meeting over-privileged execution: a deleted directory, a force-push, a command run with the wrong
account's reach. With no credentials and no write access outside the projects tree, those stay
small. It is not hardened against an agent working to get around it and does not try to be. This is
a skating helmet with elbow and knee guards, not plate mail.

## CAVEATS and tradeoffs

- *Experimental*
  - The experiment has, up to now, worked for me. I may ditch this if the complexity + coverage gaps
    outweigh the benefit
  - It is a long checklist. In just 47 easy steps of only 12 sub-parts each, you too can have the
    moderate agent harness protection of your dreams...
- Up sides
  - Provides agent uncomplicated access to machine hardware for running and testing - GPU & audio
    I/O in particular
  - No container management overhead
- Terminal only
  - Letting `agent-user` open windows in your display session would be a mess to set up on macOS, if
    it was even possible
- The boundary covers what the agent runs, not what you run
  - If you run AI produced code as yourself (as in debugging from your IDE or a via a git hook) you
    are extending trust
  - This is the part where the 'not hack proof' is trivially obvious

## Files in this directory

- `privileged-user/dotzshrc`: your interactive shell additions - `au` (agent shell in the current
  directory), `audo` (one command as the agent), `aushare` (share paths with the agent through group
  ownership and group write; `--give` hands them to the agent as owner too), decoys for the agent
  CLIs so you never run them as yourself, and the `git` function described in Conventions below.
- `agent-user/dotzshenv`, `agent-user/dotzshrc`: the agent account's shell files.

## Conventions the checklists implement

- **umask 002** for the agent and for you when touching the projects tree, so each account can edit
  what the other created.
- **No credentials for the agent.** No ssh keys, no `gh` login, no cloud login. A read-only deploy
  key is the most it gets.
- **Network git is yours, everything else is the agent's.** Your `git` function passes `clone`,
  `fetch`, `pull`, `push`, `status`, and `lfs` (plus `help`, `version` and `--version`) through and
  refuses the rest (`status`, `log`, `commit`, ...), which is done from the agent shell.
  `command git` is the deliberate way past it.

## macOS checklist

Done once per machine unless marked as done once per clone.

1. Create the account and group.
   ```
   sudo sysadminctl -addUser agent-user -fullName "Agent Sandbox User" -password -
   sudo dscl . -create /Users/agent-user IsHidden 1
   sudo dscl . -create /Groups/agent-group PrimaryGroupID 550
   sudo dscl . -create /Groups/agent-group RealName "Agent Sandbox Group"
   sudo dscl . -append /Groups/agent-group GroupMembership agent-user
   sudo dscl . -create /Users/agent-user PrimaryGroupID 550
   sudo dscl . -append /Groups/agent-group GroupMembership <you>
   ```
   Do not make `agent-group` your own primary group.
2. Password-free identity switch. `sudo visudo -f /etc/sudoers.d/me-to-agent-user`:
   ```
   <you> ALL=(agent-user) NOPASSWD: ALL
   <you> ALL=(root) NOPASSWD: /usr/bin/su - agent-user, /usr/bin/su - agent-user -c *
   Defaults>agent-user umask=0002, umask_override
   ```
   The `Defaults` line keeps `audo` output group-writable; `audo umask` should print `0002`.
3. Append `privileged-user/dotzshrc` to your `~/.zshrc` (or source it from there). Add a decoy alias
   for each agent CLI you use. `sudo -u agent-user claude` does not work (sudo is not a full
   identity switch); use `au`.
4. Agent dotfiles: copy `agent-user/dotzshenv` to `~agent-user/.zshenv` and `agent-user/dotzshrc` to
   `~agent-user/.zshrc`. `.zshenv` puts Homebrew and your `~/.local/bin` on the agent's path, wires
   up cargo, pyenv and nvm from the agent's own home for any it installs there, and sets
   `umask 002`. Edit one line: `SB_OWNER_HOME` in `setup-env` is your home; `PROJECTS_DIR` derives
   from it. `.zshrc` defines `cdp` for that tree and `cd`s to the directory `au` was run from. Trim
   the rest to taste.
5. Give yourself the agent's home and port existing agent state.
   ```
   sudo -u agent-user chmod -R g+rwX ~agent-user
   cp -r ~/.claude ~agent-user/.claude && sudo chown -R agent-user:agent-group ~agent-user/.claude
   cp ~/.gitconfig ~agent-user/ && sudo chown agent-user:agent-group ~agent-user/.gitconfig
   ```
   Do not copy `~/.ssh`, and do not log the agent in to `gh`, `gcloud` or any other backend. Signed
   commits are not supported: the agent holds no signing key, so remove `commit.gpgsign` and
   `user.signingkey` from its copy of `.gitconfig` or every agent commit fails.
6. Git configuration, run as both you and `agent-user`. `command git` bypasses the `git` function
   from step 4, which refuses everything but network operations:
   ```
   command git config --global core.sharedRepository group
   command git config --global --replace-all safe.directory '<projects-dir>/*'
   ```
7. Projects tree. Not `$HOME` itself and not `Documents/` or another special-access directory; a
   subdirectory such as `~agent-user/projects` is good. Everything under projects should be shared.
   if you're moving projects, transfer ownership (`aushare` defined in privileged-user/dotzshrc)
   ```
   cd <projects-dir> && aushare -g .
   ```
   Outside this tree, `/tmp`, its own `$TMPDIR` and its own home, the machine is read-only to the
   agent.
8. Per clone, as you: `git clone <url>` inside the projects tree, `aushare -g <clone-dir>`
   gives repo to agent-user:agent-group
9. Tell the agent (last section) and use it:
    ```
    me@mac ~ % cd ~/projects/some-repo
    me@mac some-repo % au
    agent-user@mac some-repo % claude
    ```
    The agent's first `claude` needs `/login`: open the URL it prints in your own browser, then
    paste the auth code back into the agent's session.

## Linux checklist

Same shape; the platform commands differ. Not yet exercised by the author (YMMV)

1. Account and group.
   ```
   sudo groupadd -g 550 agent-group
   sudo useradd -m -g agent-group -s /bin/bash agent-user
   sudo usermod -aG agent-group <you>
   ```
   To keep it off the login screen, with AccountsService:
   `sudo sh -c 'printf "[User]\nSystemAccount=true\n" > /var/lib/AccountsService/users/agent-user'`.
   Log out and in again for the new group membership to take effect.
2. Sudoers, `sudo visudo -f /etc/sudoers.d/me-to-agent-user`:
   ```
   <you> ALL=(agent-user) NOPASSWD: ALL
   <you> ALL=(root) NOPASSWD: /bin/su - agent-user
   Defaults>agent-user umask=0002, umask_override
   ```
   Check the `su` path with `command -v su`; sudoers needs the exact one.
3. `privileged-user/dotzshrc` in your shell rc (`~/.bashrc` if your shell is bash) as on macOS.
4. Agent dotfiles: the same two files, translated to the agent's login shell (`.bashrc` and
   `.profile`, or zsh if installed) with the Homebrew paths dropped. `umask 002` and the `cd` to the
   `au` directory are the lines that matter.
5. Agent home and state as on macOS (`sudo -u agent-user chmod -R g+rwX ~agent-user`; copy `.claude`
   and `.gitconfig`; never `.ssh` or a logged-in `gh`).
6. Git configuration for both accounts, as on macOS.
8. Projects tree: Linux does not inherit a directory's group by default, so set setgid on the tree
   as well:
   ```
   cd <projects-dir> && aushare -g . && find . -type d -exec chmod g+s {} +
   ```
9. Per clone as on macOS.
10. Display: X11 with a permissive `xhost` lets another local user open windows; Wayland does not by
    default. Your call on whether to allow agent access to your display.
11. Tell the agent (last section) before first use, as on macOS.


## Telling the agent

Add to `~agent-user/.claude/CLAUDE.md` or `~agent-user/.opencode/AGENTS.md` (create if absent):

```
## Sandbox discipline
claude-code and agent processes run in an auth sandbox as unprivileged user
`agent-user` of group `agent-group`. Neither the main session nor agents can
launch GUI applications: a process started by agent-user cannot open a window
on the primary user's display.

The user executes manual work with agent-user credentials excepting commands
requiring explicitly gated permissions (display and remote repo access).

**INVARIANT**: if you encounter an obstruction related to the sandbox *DO NOT*
attempt to circumvent it. Surface the error and stop pursuing that goal and
any other goal it gates. A path you cannot read, write or modify at your
permission level is a halting event.
```
