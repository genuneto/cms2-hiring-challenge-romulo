# AI trail

## Setup
- Tool: Claude, in a project containing the challenge brief (`BNamericas-Technical-Challenge.pdf`).
- Context given before any code: the brief, then the starter repo's `README.md` and `upstream/README.md`, `upstream/records_api/main.py`, `seed.py` and its tests, all read before designing.
- Context left behind for the tooling: `CLAUDE.md` at the repo root (hard rules, layout, upstream habits, design invariants, commands).
- Prompt that started the work: "Read the briefing document and let's tackle the 1st part."

## What the session shows (factual)
- The design came first: the upstream's habits were read from its source, then a stateless three-way merge was chosen over version numbers because of the two production constraints in the brief (three instances, nightly job writing directly).
- The backend was written and tested before the frontend. Its tests run the real upstream app in process with scripted faults.
- After the 29 tests first passed, two deliberate breakages (disable the lock, disable conflict detection) confirmed the tests fail when they should.
- A scripted end-to-end run used the real services with the upstream's default faults.
- Mistakes and corrections during the session: a `pkill -f` pattern killed the shell that ran it, so services were restarted by PID; MUI 9 rejected `alignItems` as a `Stack` prop, fixed with `sx`.
- Not done by the tool: the UI was never opened in a browser.

## How I approached the task before writing code
I started in a Claude project that held the brief, plus a local folder for the work. I did not write my own design before prompting. I asked the tool to read the brief and tackle part 1, and my first instruction was only “Read the briefing document. I have already cloned the repo locally and the task at hand is the 1st implementation part, specifically respecting the stated rules and the concurrency requirements”

Before any code was written, the tool read the starter README.md, upstream/README.md, the upstream’s main.py, its seed data and its tests. It also ran the upstream and fetched a record. Only then did it choose the design: a stateless three-way merge against the live upstream record rather than version numbers. The reasons were the brief’s two production constraints, three backend instances and a nightly job that writes to the upstream directly. A counter kept in my own storage would not have seen that job. I accepted this design. I did not propose it.

## Where the tool carried the work, where I overrode it, what I checked by hand (yours to write)
Carried. The tool did nearly all the engineering: the merge rules, the save loop, the handling of the upstream’s 504s, the API, the React forms and conflict dialog, 29 tests, CLAUDE.md, DECISIONS.md and the README. It also checked its own tests by breaking the lock and the conflict rule on purpose and confirming they failed. It ran an end-to-end script against the real services with the upstream’s faults on.
Overrode. I did not override a design or code decision while the tool was building.
Checked by hand. On my own machine I ran the backend tests (29 passed) and the frontend build, and confirmed upstream/ was unchanged. I also sorted out the GitHub account mismatch and the commit author identity. 
I opened the same project in two browser tabs and ran the conflict flow. I read merge.py line by line.
The UI was never exercised in a browser by the tool, and I have done that check myself.
