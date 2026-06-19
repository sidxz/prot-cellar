export function parseFasta(text: string): { header: string; sequence: string } {
  const lines = text.split("\n");
  let header = "";
  const residues: string[] = [];
  for (const line of lines) {
    if (line.startsWith(">")) {
      header = line.slice(1).trim();
      continue;
    }
    residues.push(line.replace(/\s+/g, ""));
  }
  return { header, sequence: residues.join("") };
}

export function chunkSequence(seq: string, perLine = 60): string[] {
  const out: string[] = [];
  for (let i = 0; i < seq.length; i += perLine) out.push(seq.slice(i, i + perLine));
  return out;
}

export function toFasta(header: string, seq: string, width = 60): string {
  return [`>${header}`, ...chunkSequence(seq, width)].join("\n");
}
