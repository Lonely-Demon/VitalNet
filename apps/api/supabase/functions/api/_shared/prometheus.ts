// Minimal Prometheus text exposition formatter (v0.0.4 — the same format
// prometheus_client's generate_latest() produces). Deno has no
// prometheus_client equivalent, and this app doesn't need one: it renders
// one Counter, not a full metrics registry.

export const PROMETHEUS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8";

export interface CounterSample {
  labels: Record<string, string>;
  value: number;
}

function escapeLabelValue(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\n/g, "\\n");
}

function formatLabels(labels: Record<string, string>): string {
  const pairs = Object.entries(labels).map(([k, v]) => `${k}="${escapeLabelValue(v)}"`);
  return pairs.length ? `{${pairs.join(",")}}` : "";
}

/** Renders one Counter metric (HELP/TYPE header + one line per sample). */
export function renderCounter(name: string, help: string, samples: CounterSample[]): string {
  const lines = [`# HELP ${name} ${help}`, `# TYPE ${name} counter`];
  for (const sample of samples) {
    lines.push(`${name}${formatLabels(sample.labels)} ${sample.value}`);
  }
  return lines.join("\n") + "\n";
}
