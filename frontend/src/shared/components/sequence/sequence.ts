export function chunkSequence(seq: string, perLine = 60): string[] {
  const out: string[] = [];
  for (let i = 0; i < seq.length; i += perLine) out.push(seq.slice(i, i + perLine));
  return out;
}

export function toFasta(header: string, seq: string, width = 60): string {
  return [`>${header}`, ...chunkSequence(seq, width)].join("\n");
}
