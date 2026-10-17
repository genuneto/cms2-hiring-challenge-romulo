import { Alert, Box, Button, MenuItem, Stack, TextField, Typography } from "@mui/material";
import { useEffect, useState } from "react";
import { ApiError, getOptions, getProject, saveProject, type Conflict, type Editable, type Options, type SaveResult } from "./api";
import ConflictDialog from "./ConflictDialog";
import { applyChoices, describeKey, hasDuplicateLabels, humanize, sameEditable, toEditable } from "./model";

type Notice = { severity: "success" | "error" | "warning"; text: string };
type Pending = { current: Editable; conflicts: Conflict[]; proposed: Editable };

export default function ProjectEditor({ id, onBack }: { id: string; onBack: () => void }) {
  const [options, setOptions] = useState<Options | null>(null);
  const [base, setBase] = useState<Editable | null>(null); // the version this form was loaded from, sent with every save
  const [draft, setDraft] = useState<Editable | null>(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = () => {
    setLoadError(null);
    getProject(id).then(
      (p) => {
        setBase(toEditable(p));
        setDraft(toEditable(p));
      },
      (e: Error) => setLoadError(e.message),
    );
  };

  useEffect(() => {
    getOptions().then(setOptions, (e: Error) => setLoadError(e.message));
    load();
  }, [id]);

  if (loadError) return <Alert severity="error" action={<Button onClick={load}>Retry</Button>}>{loadError}</Alert>;
  if (!draft || !base || !options) return <Typography>Loading…</Typography>;

  const dirty = !sameEditable(draft, base);
  const duplicateLabels = hasDuplicateLabels(draft.key_dates) && !hasDuplicateLabels(base.key_dates);
  const invalid = !draft.name || !draft.country || draft.key_dates.some((d) => !d.label || !d.date) || duplicateLabels;

  const set = <K extends keyof Editable>(key: K, value: Editable[K]) => setDraft({ ...draft, [key]: value });
  const setDate = (i: number, patch: Partial<Editable["key_dates"][number]>) =>
    set("key_dates", draft.key_dates.map((d, j) => (j === i ? { ...d, ...patch } : d)));

  const submit = async (from: Editable, edited: Editable) => {
    setSaving(true);
    setNotice(null);
    let result: SaveResult;
    try {
      result = await saveProject(id, from, edited);
    } catch (e) {
      const err = e as ApiError;
      const text =
        err.saved === "unknown"
          ? `${err.message} Your change may or may not have been saved. Reload to see what is stored before trying again.`
          : err.saved === "no"
            ? `${err.message} Your edits are still here; try saving again.`
            : err.message;
      setNotice({ severity: "error", text });
      setPending(null);
      setSaving(false);
      return;
    }
    setSaving(false);

    if (result.kind === "conflict") {
      setPending({ current: toEditable(result.current), conflicts: result.conflicts, proposed: result.proposed });
      return;
    }
    const saved = toEditable(result.project);
    setBase(saved);
    setDraft(saved);
    setPending(null);
    const others = result.alsoChangedByOthers;
    setNotice({
      severity: "success",
      text: others.length ? `Saved. These fields had also been changed by someone else and are now up to date here: ${others.map(describeKey).join(", ")}.` : "Saved.",
    });
  };

  const resolve = (choices: Record<string, "mine" | "theirs">) => {
    if (!pending) return;
    // The next request starts from what is stored NOW, so a value that moves again is a new conflict, not an overwrite.
    submit(pending.current, applyChoices(pending.proposed, pending.conflicts, choices));
  };

  return (
    <Box>
      <Button onClick={onBack} sx={{ mb: 1 }}>
        ← All projects
      </Button>
      <Typography variant="h5" sx={{ mb: 2 }}>
        {id}
      </Typography>
      {notice && (
        <Alert severity={notice.severity} sx={{ mb: 2 }} onClose={() => setNotice(null)}>
          {notice.text}
        </Alert>
      )}
      <Stack spacing={2} sx={{ maxWidth: 640 }}>
        <TextField label="Name" value={draft.name} onChange={(e) => set("name", e.target.value)} error={!draft.name} required />
        <TextField label="Country" value={draft.country} onChange={(e) => set("country", e.target.value)} error={!draft.country} required />
        <TextField select label="Sector" value={draft.sector} onChange={(e) => set("sector", e.target.value)}>
          {options.sectors.map((s) => (
            <MenuItem key={s} value={s}>
              {humanize(s)}
            </MenuItem>
          ))}
        </TextField>
        <TextField select label="Stage" value={draft.stage} onChange={(e) => set("stage", e.target.value)}>
          {options.stages.map((s) => (
            <MenuItem key={s} value={s}>
              {humanize(s)}
            </MenuItem>
          ))}
        </TextField>

        <Typography variant="subtitle1">Key dates</Typography>
        {draft.key_dates.map((d, i) => (
          <Stack key={i} direction="row" spacing={1} sx={{ alignItems: "flex-start" }}>
            <TextField label="Label" size="small" value={d.label} onChange={(e) => setDate(i, { label: e.target.value })} sx={{ flex: 1 }} />
            <TextField
              label="Date"
              type="date"
              size="small"
              value={d.date}
              onChange={(e) => setDate(i, { date: e.target.value })}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <Button color="error" onClick={() => set("key_dates", draft.key_dates.filter((_, j) => j !== i))}>
              Remove
            </Button>
          </Stack>
        ))}
        {duplicateLabels && <Alert severity="warning">Each key date needs its own label.</Alert>}
        <Box>
          <Button onClick={() => set("key_dates", [...draft.key_dates, { label: "", date: "" }])}>Add key date</Button>
        </Box>

        <Stack direction="row" spacing={1}>
          <Button variant="contained" disabled={!dirty || invalid || saving} onClick={() => submit(base, draft)}>
            {saving ? "Saving…" : "Save"}
          </Button>
          <Button disabled={saving} onClick={load}>
            {dirty ? "Discard changes and reload" : "Reload"}
          </Button>
        </Stack>
      </Stack>

      {pending && <ConflictDialog key={JSON.stringify(pending.conflicts)} conflicts={pending.conflicts} busy={saving} onResolve={resolve} onCancel={() => setPending(null)} />}
    </Box>
  );
}
