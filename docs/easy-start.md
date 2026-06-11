# Easy Start (no experience needed)

Your own AI helper, on your own computer. Free. Private. No account.

## Step 1 - Install

Copy ONE line, paste it, press Enter.

**Windows** - press the Windows key, type `powershell`, press Enter, then paste:

```text
irm https://raw.githubusercontent.com/DevEpoch/lai/main/install.ps1 | iex
```

**Mac or Linux** - open Terminal, then paste:

```text
curl -fsSL https://raw.githubusercontent.com/DevEpoch/lai/main/install.sh | bash
```

## Step 2 - Say "go"

Close that window, open a NEW one (the install added the `lai` command -
new windows know about it, old ones don't). Then type:

```text
lai go
```

lai introduces itself and asks ONE question (yes/no) before downloading your
AI. Say yes and wait - you can watch the progress bars, and it is safe to
keep using the computer. If the download stops for any reason, just run
`lai go` again; it continues where it left off.

## Step 3 - Talk to it

When it says **ALL DONE**, a "Local AI Env" icon is on your Desktop.
Double-click it. You will see a green light that says **Your AI is ready!**

Type in the chat box, for example:

```text
write a snake game in Python
```

That's it. Your AI answers from YOUR computer - no internet needed anymore,
and nothing you type goes anywhere.

## Questions kids (and grown-ups) ask

- **Is it really free?** Yes. The AI models are open and free; lai itself is
  free and open source.
- **Does it need internet?** Only for the first download. After that, no.
- **Can it see what I type?** Only your computer can. Nothing is sent to any
  company.
- **Where is the dashboard (the UI)?** Double-click the **Local AI Env**
  icon on your Desktop, or type `lai ui`, or open
  `http://localhost:8090` in your browser. All three are the same place.
- **It says `lai` is not recognized?** Open a NEW terminal window (old
  ones don't know new commands). Still not working? Type
  `python lai.py path` inside the lai folder once, then open a new window.
- **It says a port is busy?** Type `lai ports check --fix` and say yes - lai
  politely moves out of the way.
- **Something looks stuck?** Type `lai info` to see what's going on, or
  `lai go` to make it pick up where it stopped.
- **I want to build a real app!** Open the dashboard, click **Projects**,
  pick what you want to make, choose a folder - lai builds the starting
  point and your AI helps you grow it.
