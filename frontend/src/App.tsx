import { AppBar, Container, CssBaseline, Toolbar, Typography } from "@mui/material";
import { useEffect, useState } from "react";
import ProjectEditor from "./ProjectEditor";
import ProjectList from "./ProjectList";

// Hash routing keeps this dependency-free: #/projects/P-1001 opens a project, anything else shows the list.
const readRoute = () => /^#\/projects\/([^/]+)$/.exec(window.location.hash)?.[1] ?? null;

export default function App() {
  const [projectId, setProjectId] = useState<string | null>(readRoute());

  useEffect(() => {
    const onChange = () => setProjectId(readRoute());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  return (
    <>
      <CssBaseline />
      <AppBar position="static" color="default" elevation={0}>
        <Toolbar>
          <Typography variant="h6">Project editor</Typography>
        </Toolbar>
      </AppBar>
      <Container sx={{ py: 3 }}>
        {projectId ? (
          <ProjectEditor id={decodeURIComponent(projectId)} onBack={() => (window.location.hash = "")} />
        ) : (
          <ProjectList onOpen={(id) => (window.location.hash = `/projects/${encodeURIComponent(id)}`)} />
        )}
      </Container>
    </>
  );
}
