import { useEffect, useState } from "react";
import { Cloud, Code2, Cpu, Moon, Radio, Sun } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { ConnectionState, EngineMode } from "@/lib/types";
import { cn } from "@/lib/utils";

const REPO_URL = "https://github.com/ErenAksu17/python-data-projects/tree/main/SyntheticData%2BAI";

interface Props {
  mode: EngineMode;
  requestedMode: EngineMode | "auto";
  onModeChange: (mode: EngineMode | "auto") => void;
  connection: ConnectionState;
}

export function Header({ mode, requestedMode, onModeChange, connection }: Props) {
  return (
    <header className="border-border/80 bg-background/80 sticky top-0 z-20 border-b backdrop-blur-md">
      <div className="mx-auto flex max-w-[1500px] flex-wrap items-center gap-3 px-4 py-3 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <div className="bg-primary/12 text-primary grid size-9 shrink-0 place-items-center rounded-lg">
            <Radio className="size-4.5" />
          </div>
          <div className="min-w-0">
            <h1 className="truncate text-base leading-tight font-semibold tracking-tight">
              Virtual Factory
            </h1>
            <p className="text-muted-foreground truncate text-xs">
              Vibration monitoring · autoencoder anomaly detection
            </p>
          </div>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <ConnectionBadge mode={mode} connection={connection} />

          <Tabs
            value={requestedMode}
            onValueChange={(value) => onModeChange(value as EngineMode | "auto")}
          >
            <TabsList>
              <TabsTrigger value="auto">Auto</TabsTrigger>
              <TabsTrigger value="live" className="gap-1.5">
                <Cloud className="size-3.5" />
                API
              </TabsTrigger>
              <TabsTrigger value="offline" className="gap-1.5">
                <Cpu className="size-3.5" />
                Browser
              </TabsTrigger>
            </TabsList>
          </Tabs>

          <ThemeToggle />

          <Button variant="ghost" size="icon" asChild aria-label="Source on GitHub">
            <a href={REPO_URL} target="_blank" rel="noreferrer noopener">
              <Code2 />
            </a>
          </Button>
        </div>
      </div>
    </header>
  );
}

function ConnectionBadge({
  mode,
  connection,
}: {
  mode: EngineMode;
  connection: ConnectionState;
}) {
  const live = connection === "open";
  const label =
    connection === "open"
      ? mode === "live"
        ? "Streaming"
        : "In browser"
      : connection === "connecting"
        ? "Connecting"
        : connection === "closed"
          ? "Disconnected"
          : "Unavailable";

  return (
    <Badge
      variant={live ? "success" : connection === "error" ? "destructive" : "secondary"}
      className="gap-1.5"
    >
      <span
        className={cn(
          "size-1.5 rounded-full",
          live ? "live-dot bg-[var(--success)]" : "bg-muted-foreground",
        )}
      />
      {label}
    </Badge>
  );
}

const STORAGE_KEY = "vfactory-theme";

function ThemeToggle() {
  const [dark, setDark] = useState(() => {
    if (typeof window === "undefined") return true;
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored) return stored === "dark";
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    document.documentElement.style.colorScheme = dark ? "dark" : "light";
    window.localStorage.setItem(STORAGE_KEY, dark ? "dark" : "light");
  }, [dark]);

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setDark((value) => !value)}
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
    >
      {dark ? <Sun /> : <Moon />}
    </Button>
  );
}
