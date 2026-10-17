import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Paper,
  Radio,
  RadioGroup,
  Stack,
  Typography,
} from "@mui/material";
import { useState } from "react";
import type { Conflict } from "./api";
import { describeKey, describeValue } from "./model";

type Choices = Record<string, "mine" | "theirs">;

/**
 * Someone saved a field you also changed. Nothing has been written. Each conflict needs an explicit choice, with
 * no default: the second person to save decides, and decides on purpose.
 */
export default function ConflictDialog({
  conflicts,
  busy,
  onResolve,
  onCancel,
}: {
  conflicts: Conflict[];
  busy: boolean;
  onResolve: (choices: Choices) => void;
  onCancel: () => void;
}) {
  const [choices, setChoices] = useState<Choices>({});
  const allChosen = conflicts.every((c) => choices[c.key]);

  return (
    <Dialog open fullWidth maxWidth="sm" onClose={busy ? undefined : onCancel}>
      <DialogTitle>Someone else changed this at the same time</DialogTitle>
      <DialogContent>
        <Typography sx={{ mb: 2 }}>
          Your other changes are ready to save. Choose which value to keep for {conflicts.length === 1 ? "this field" : "each of these fields"}.
        </Typography>
        <Stack spacing={2}>
          {conflicts.map((c) => (
            <Paper key={c.key} variant="outlined" sx={{ p: 2 }}>
              <Typography variant="subtitle2">{describeKey(c.key)}</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                You started from: {describeValue(c.base)}
              </Typography>
              <RadioGroup value={choices[c.key] ?? ""} onChange={(e) => setChoices({ ...choices, [c.key]: e.target.value as "mine" | "theirs" })}>
                <FormControlLabel value="theirs" control={<Radio />} label={`Keep what was saved: ${describeValue(c.theirs)}`} />
                <FormControlLabel value="mine" control={<Radio />} label={`Use mine: ${describeValue(c.mine)}`} />
              </RadioGroup>
            </Paper>
          ))}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel} disabled={busy}>
          Back to my edits
        </Button>
        <Button variant="contained" disabled={!allChosen || busy} onClick={() => onResolve(choices)}>
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
}
