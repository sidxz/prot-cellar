import type { ReactNode } from "react";

/** Render text with inline `PubMed:NNNN` tokens turned into links to PubMed. */
export function linkifyPubmed(text: string): ReactNode[] {
  const regex = /PubMed:(\d+)/g;
  const nodes: ReactNode[] = [];
  let lastIndex = 0;
  let match = regex.exec(text);

  while (match !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    const pmid = match[1];
    nodes.push(
      <a
        key={`pubmed-${match.index}-${pmid}`}
        href={`https://pubmed.ncbi.nlm.nih.gov/${pmid}/`}
        target="_blank"
        rel="noopener noreferrer"
        className="text-primary hover:underline"
      >
        PubMed:{pmid}
      </a>,
    );
    lastIndex = match.index + match[0].length;
    match = regex.exec(text);
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }
  return nodes;
}
