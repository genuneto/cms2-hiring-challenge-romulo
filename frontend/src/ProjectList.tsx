import { Alert, Box, CircularProgress, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography } from "@mui/material";
import { useEffect, useMemo, useState } from "react";
import { listProjects, type Summary } from "./api";
import { humanize } from "./model";

export default function ProjectList({ onOpen }: { onOpen: (id: string) => void }) {
  const [projects, setProjects] = useState<Summary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    listProjects().then(setProjects, (e: Error) => setError(e.message));
  }, []);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (projects ?? []).filter((p) => !q || [p.id, p.name, p.country, p.sector, p.stage].some((v) => v.toLowerCase().includes(q)));
  }, [projects, query]);

  if (error) return <Alert severity="error">{error}</Alert>;
  if (!projects) return <CircularProgress aria-label="Loading projects" />;

  return (
    <Box>
      <TextField label="Filter" size="small" value={query} onChange={(e) => setQuery(e.target.value)} sx={{ mb: 2, minWidth: 280 }} />
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>ID</TableCell>
            <TableCell>Name</TableCell>
            <TableCell>Sector</TableCell>
            <TableCell>Country</TableCell>
            <TableCell>Stage</TableCell>
            <TableCell align="right">Key dates</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {shown.map((p) => (
            <TableRow key={p.id} hover sx={{ cursor: "pointer" }} onClick={() => onOpen(p.id)}>
              <TableCell>{p.id}</TableCell>
              <TableCell>{p.name}</TableCell>
              <TableCell>{humanize(p.sector)}</TableCell>
              <TableCell>{p.country}</TableCell>
              <TableCell>{humanize(p.stage)}</TableCell>
              <TableCell align="right">{p.key_dates_count}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {shown.length === 0 && <Typography sx={{ mt: 2 }}>No projects match.</Typography>}
    </Box>
  );
}
